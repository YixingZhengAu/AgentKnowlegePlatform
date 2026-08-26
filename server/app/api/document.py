"""文档 RAG(S2)的 REST 接口:上传 → 五步摄取 → 审核切片 → 发布。

**切片候选的列表与编辑不在这里** —— 它们走 S0 的通用审核接口
(`GET /api/staging?job_id=`、`PATCH /api/staging/{id}`、`POST /api/jobs/{id}/publish`),
因为"筛选/编辑/批量/发布"对三类知识是同一套流程。本文件只放本域独有的动作:

| 动作 | 端点 | 为什么不能通用化 |
| --- | --- | --- |
| 上传 PDF 并启动摄取 | `POST /api/document/documents` | 建 source+document+job 是本域的三件事 |
| 文档列表 / 详情 | `GET /api/document/documents[/{id}]` | 阶段与切片数由本域的表推导 |
| 合并相邻切片 | `POST .../candidates/{id}/merge-next` | 只有切片有"相邻"这个概念 |
| 删除文档 | `DELETE .../documents/{id}` | 要一起清掉解析产物、切片与 Job |
| 检索自检 | `GET /api/document/search` | 演示与冒烟要能直接看到混合检索的真实名次 |

图片出口复用 `api/files.py`(按 document_id 寻址,不分域)。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.config import settings
from app.core.errors import ConflictError, NotFoundError
from app.core.jobs import execute_job, submit_job
from app.core.logging import get_logger
from app.core.staging import get_item
from app.models import Chunk as ChunkRow
from app.models import Document, IngestJob, IngestSource, KnowledgeBase, StagingItem
from app.providers import get_embedder
from app.schemas.common import ListResponse
from app.schemas.document import (
    Chunk,
    ChunkDetail,
    ChunkMergeResult,
    ChunkStatusResult,
    DocumentStage,
    DocumentSummary,
    IngestSubmitted,
    PublishedChunk,
    ReingestSubmitted,
    SearchHit,
    SearchRecall,
    SearchResult,
    chunk_is_retired,
    embed_input,
)
from app.services.document import storage
from app.services.document.ingest import JOB_TYPE
from app.services.document.retriever import retrieve

router = APIRouter(prefix="/api/document", tags=["document"])
log = get_logger(__name__)

ALLOWED_MIME = ("application/pdf",)
MAX_UPLOAD_MB = 50


# ─── 私有助手 ─────────────────────────────────────────────────────────────────

async def _default_kb(session: SessionDep) -> KnowledgeBase | None:
    """本域的默认知识库 —— 没显式指定 kb_id 时用最早建的那个 active 库。"""
    stmt = (
        select(KnowledgeBase)
        .where(KnowledgeBase.type == "document", KnowledgeBase.status == "active")
        .order_by(KnowledgeBase.created_at)
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


def _stage(doc: Document, job_status: str | None) -> DocumentStage:
    """界面上的阶段 —— 由解析态 + Job 状态推导,**不新增列**。"""
    if doc.parse_status == "failed" or job_status == "failed":
        return "failed"
    if job_status == "published":
        return "published"
    if job_status == "review":
        return "review"
    if doc.parse_status in ("pending", "parsing") or job_status in ("queued", "running"):
        return "ingesting" if job_status in ("queued", "running") else "pending"
    return "pending"


async def _rows(session: SessionDep, doc_ids: list[uuid.UUID]) -> tuple[dict, dict]:
    """一次查出这批文档的 Job 状态与切片数(避免 N+1)。"""
    if not doc_ids:
        return {}, {}
    # 🩸 用 jsonb 取值过滤,别把全部 doc_ingest job 拉回来在 Python 里筛 ——
    # job 表只增不减,那样做的代价随演示时长线性增长。
    doc_key = IngestJob.params["document_id"].astext
    jobs = (
        (
            await session.execute(
                select(IngestJob)
                .where(
                    IngestJob.job_type == JOB_TYPE,
                    doc_key.in_([str(d) for d in doc_ids]),
                )
                .order_by(IngestJob.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    by_doc: dict[uuid.UUID, IngestJob] = {}
    for job in jobs:
        # 同一份文档可能重跑过多次,取最新那一个(上面已按创建时间倒序)
        by_doc.setdefault(uuid.UUID(str(job.params["document_id"])), job)

    # 只数 active:退休行(被引用过、重新发布时留下的)不该让这个数字虚高 ——
    # 它们已经不在任何检索里了,列表上却显示成"这份文档有 N 条切片"会误导
    counts = dict(
        (
            await session.execute(
                select(ChunkRow.doc_id, func.count(ChunkRow.id))
                .where(ChunkRow.doc_id.in_(doc_ids), ChunkRow.status == "active")
                .group_by(ChunkRow.doc_id)
            )
        ).all()
    )
    return by_doc, counts


def _out(doc: Document, job: IngestJob | None, chunks: int) -> DocumentSummary:
    """拼一行文档出参。"""
    return DocumentSummary(
        id=doc.id,
        name=doc.name,
        size_bytes=doc.size_bytes,
        parse_status=doc.parse_status,
        parse_error=doc.parse_error,
        created_at=doc.created_at,
        stage=_stage(doc, job.status if job else None),
        ingest_job_id=job.id if job else None,
        chunk_count=chunks,
        page_count=(doc.meta or {}).get("page_count"),
    )


# ─── 文档 ─────────────────────────────────────────────────────────────────────

@router.post("/documents", response_model=IngestSubmitted, status_code=201)
async def upload_document(
    session: SessionDep,
    user: CurrentUser,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File(description="PDF only (S2 boundary)")],
    kb_id: uuid.UUID | None = None,
) -> IngestSubmitted:
    """上传一份 PDF 并立刻启动五步摄取。"""
    if file.content_type not in ALLOWED_MIME:
        raise ConflictError(
            f"Document RAG only accepts PDF (got {file.content_type})",
            code="unsupported_file_type",
        )
    data = await file.read()
    if not data:
        raise ConflictError("The uploaded file is empty", code="empty_upload")
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ConflictError(f"File exceeds {MAX_UPLOAD_MB} MB", code="file_too_large")

    kb = await session.get(KnowledgeBase, kb_id) if kb_id else await _default_kb(session)
    if kb is None:
        raise NotFoundError(f"Knowledge base {kb_id} not found")

    name = file.filename or "upload.pdf"
    source = IngestSource(
        kb_id=kb.id,
        source_type="file",
        original_name=name,
        size_bytes=len(data),
        mime=file.content_type,
        uploaded_by=user.id,
    )
    session.add(source)
    await session.flush()  # 要 source.id 才能给文件命名
    source.uri = storage.save_source_pdf(str(source.id), data)

    doc = Document(
        kb_id=kb.id,
        source_id=source.id,
        name=name,
        file_type="pdf",
        raw_uri=source.uri,
        size_bytes=len(data),
        parse_status="pending",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    job = await submit_job(
        job_type=JOB_TYPE,
        kb_id=kb.id,
        source_id=source.id,
        params={"document_id": str(doc.id)},
        created_by=user.id,
    )
    doc.meta = {**(doc.meta or {}), "ingest_job_id": str(job.id)}
    await session.commit()
    background.add_task(execute_job, job.id)
    log.info("document_uploaded", document_id=str(doc.id), job_id=str(job.id), bytes=len(data))
    return IngestSubmitted(document_id=doc.id, source_id=source.id, job_id=job.id)


@router.get("/documents", response_model=ListResponse[DocumentSummary])
async def list_documents(
    session: SessionDep,
    kb_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListResponse[DocumentSummary]:
    """文档列表(最新在前)。"""
    stmt = select(Document).join(KnowledgeBase, KnowledgeBase.id == Document.kb_id)
    stmt = stmt.where(KnowledgeBase.type == "document")
    if kb_id is not None:
        stmt = stmt.where(Document.kb_id == kb_id)
    total = int(
        (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    docs = (
        (await session.execute(stmt.order_by(Document.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    jobs, counts = await _rows(session, [d.id for d in docs])
    return ListResponse(
        items=[_out(d, jobs.get(d.id), counts.get(d.id, 0)) for d in docs], total=total
    )


@router.get("/documents/{document_id}", response_model=DocumentSummary)
async def get_document(session: SessionDep, document_id: uuid.UUID) -> DocumentSummary:
    """单份文档。"""
    doc = await session.get(Document, document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    jobs, counts = await _rows(session, [doc.id])
    return _out(doc, jobs.get(doc.id), counts.get(doc.id, 0))


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(session: SessionDep, document_id: uuid.UUID) -> None:
    """删掉文档:库里的行(切片 CASCADE)+ 磁盘上的解析产物与原件。"""
    doc = await session.get(Document, document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    raw_uri = doc.raw_uri
    await session.delete(doc)
    await session.commit()
    # 先提交再动磁盘:库里已经没有这一行了,磁盘残留只值一条 warning
    storage.remove_document_files(str(document_id), raw_uri)
    log.info("document_deleted", document_id=str(document_id))


# ─── 审核台的本域动作 ─────────────────────────────────────────────────────────

@router.post("/candidates/{item_id}/merge-next", response_model=ChunkMergeResult)
async def merge_next(
    session: SessionDep, user: CurrentUser, item_id: uuid.UUID
) -> ChunkMergeResult:
    """把这条切片与**紧随其后的那条**合并成一条。

    切分是自动的,偶尔会把一句话的上下文拆两半 —— 审核台要能就地补救。
    合并后:被并进来的那条标成 `rejected`(不再发布),本条标成 `modified`;
    🩸 **seq 不重排**(`chunks` 的 UNIQUE(doc_id, seq) 允许留空洞),
    因为重排会让"上下文扩展取前后片"在重跑之间对不上。
    """
    item = await get_item(session, item_id)
    job = await session.get(IngestJob, item.job_id)
    if job is None or job.status != "review":
        raise ConflictError("This job is not open for review", code="job_not_reviewable")

    current = Chunk.model_validate(item.payload or {})
    doc_id = (item.origin_ref or {}).get("document_id")
    siblings = (
        (
            await session.execute(
                select(StagingItem).where(
                    StagingItem.job_id == item.job_id,
                    StagingItem.item_type == item.item_type,
                    StagingItem.id != item.id,
                    StagingItem.review_status != "rejected",
                )
            )
        )
        .scalars()
        .all()
    )
    following = sorted(
        (
            s
            for s in siblings
            if (s.origin_ref or {}).get("document_id") == doc_id
            and (s.payload or {}).get("seq", -1) > current.seq
        ),
        key=lambda s: (s.payload or {}).get("seq", 0),
    )
    if not following:
        raise ConflictError("This is the last chunk; there is nothing to merge with",
                            code="no_next_chunk")

    nxt = following[0]
    other = Chunk.model_validate(nxt.payload or {})
    merged = current.model_copy(
        update={
            "content": f"{current.content}\n\n{other.content}",
            "token_count": current.token_count + other.token_count,
            "figures": [*current.figures, *other.figures],
        }
    )
    item.payload = merged.as_payload()
    item.review_status = "modified"
    item.reviewed_by = user.id
    nxt.review_status = "rejected"
    nxt.review_note = f"Merged into chunk #{current.seq}"
    nxt.reviewed_by = user.id
    await session.commit()
    log.info("document_chunks_merged", item_id=str(item.id), merged=str(nxt.id))
    return ChunkMergeResult(item_id=item.id, merged_item_id=nxt.id, token_count=merged.token_count)


# ─── 引用回显 ─────────────────────────────────────────────────────────────────


@router.get("/chunks/{chunk_id}", response_model=ChunkDetail)
async def get_chunk(session: SessionDep, chunk_id: uuid.UUID) -> ChunkDetail:
    """按 id 取一条**已发布**切片的全文与元数据 —— 答案里点开 `[n]` 走这里。

    引用面板只存 240 字摘录(`message_citations.snippet`),全文实时读库,
    历史会话因此永远显示切片的**当前**内容,而不是提问那天的快照。
    """
    row = await session.get(ChunkRow, chunk_id)
    if row is None:
        raise NotFoundError("Chunk not found", code="chunk_not_found")
    doc = await session.get(Document, row.doc_id)
    meta = row.meta or {}
    return ChunkDetail(
        id=row.id,
        document_id=row.doc_id,
        document_name=doc.name if doc else "—",
        retired=chunk_is_retired(meta),
        seq=row.seq,
        content=row.content,
        heading_path=row.heading_path,
        page_idx=meta.get("page_idx"),
        token_count=row.token_count,
        figures=meta.get("figures", []),
    )


# ─── 运营:已发布切片的管理(S2-4)────────────────────────────────────────────
#
# 边界:本节操作 `chunks` 里的**正式行**;`staging_items` 里的待审候选归上面的审核台。
# "禁用"与"不采纳"是两件事 —— 前者可逆、发生在发布之后,后者不可逆、发生在发布之前。


def _published(row: ChunkRow) -> PublishedChunk:
    meta = row.meta or {}
    return PublishedChunk(
        id=row.id,
        retired=chunk_is_retired(meta),
        seq=row.seq,
        content=row.content,
        heading_path=row.heading_path,
        page_idx=meta.get("page_idx"),
        token_count=row.token_count,
        status=row.status,
        embedded=row.embedding is not None,
        figure_count=len(meta.get("figures", [])),
    )


@router.get("/documents/{document_id}/chunks", response_model=ListResponse[PublishedChunk])
async def list_chunks(
    session: SessionDep,
    document_id: uuid.UUID,
    include_retired: bool = False,
) -> ListResponse[PublishedChunk]:
    """一份文档已发布的全部切片,按 `seq` 排。

    默认**不含退休行**(重新发布时被引用过的旧行会退休成 `disabled` 且 seq 变负数)——
    它们只为历史会话的引用还能读得到而留着,不该混在"这份文档现在是什么样"里。
    `include_retired=true` 时一并返回,用于排查"引用点开的是哪一条"。

    Args:
        document_id: 文档 id。
        include_retired: 是否带上退休行(seq < 0)。
    """
    if await session.get(Document, document_id) is None:
        raise NotFoundError(f"Document {document_id} not found")
    stmt = select(ChunkRow).where(ChunkRow.doc_id == document_id).order_by(ChunkRow.seq)
    if not include_retired:
        # jsonb 里没有 `retired` 键的就是在用的行(`->>` 对缺键返回 NULL)
        stmt = stmt.where(ChunkRow.meta["retired"].astext.is_(None))
    rows = (await session.execute(stmt)).scalars().all()
    items = [_published(r) for r in rows]
    return ListResponse(items=items, total=len(items), page=1, page_size=len(items) or 1)


@router.post("/chunks/{chunk_id}/disable", response_model=ChunkStatusResult)
async def disable_chunk(session: SessionDep, chunk_id: uuid.UUID) -> ChunkStatusResult:
    """下线一条切片:两条召回都不再返回它,历史会话里引用过它的地方照样读得到。

    **不物理删** —— `message_citations.ref_id` 可能指着它。
    同时清空 `embedding`:只改 status 的话,HNSW 索引里那条还在,是白占空间的死数据。
    """
    row = await _chunk_or_404(session, chunk_id)
    if row.status == "disabled":
        raise ConflictError("This chunk is already disabled", code="chunk_already_disabled")
    row.status = "disabled"
    row.embedding = None
    await session.commit()
    log.info("chunk_disabled", chunk_id=str(chunk_id))
    return ChunkStatusResult(id=row.id, status=row.status, embedded=False)


@router.post("/chunks/{chunk_id}/enable", response_model=ChunkStatusResult)
async def enable_chunk(session: SessionDep, chunk_id: uuid.UUID) -> ChunkStatusResult:
    """重新上线一条切片。

    🩸 **这不是纯状态变更** —— 禁用时把向量清了,所以启用要重算一次 embedding
    (一次 Embedding 调用)。前端那颗按钮必须有 loading 态,不能装成瞬时操作。
    """
    row = await _chunk_or_404(session, chunk_id)
    if chunk_is_retired(row.meta):
        # 退休行是历史引用的存根,它的正文早已被新一版取代 —— 放回去会和新行重复
        raise ConflictError(
            "This chunk was retired by a later publish and cannot be re-enabled",
            code="chunk_retired",
        )
    if row.status == "active" and row.embedding is not None:
        raise ConflictError("This chunk is already active", code="chunk_already_active")

    # 🩸 拼法必须与发布时一致 —— 所以用同一个 `embed_input()`,不在这里手拼
    text_in = embed_input(row.heading_path, row.content)
    row.embedding = (await get_embedder().embed([text_in]))[0]
    row.status = "active"
    await session.commit()
    log.info("chunk_enabled", chunk_id=str(chunk_id))
    return ChunkStatusResult(id=row.id, status=row.status, embedded=True)


@router.post("/documents/{document_id}/reingest", response_model=ReingestSubmitted, status_code=201)
async def reingest_document(
    session: SessionDep,
    user: CurrentUser,
    background: BackgroundTasks,
    document_id: uuid.UUID,
) -> ReingestSubmitted:
    """对一份已发布的文档重跑一遍五步摄取(切分参数或解析质量变了才用得上)。

    三条语义(S2-4 分册 §4 已定,不要在这里重新发明):

    1. **重跑要过人工关** —— 重跑的意义就是切分结果变了,不重审等于白跑;
    2. **重跑期间旧切片仍然 `active`** —— 比"这份文档几分钟内搜不到"好;
    3. 新的一批发布时,`replace_document_chunks` 才处理旧行(被引用过的退休,其余删)。
    """
    doc = await session.get(Document, document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    if doc.source_id is None:
        raise ConflictError(
            "The original file for this document is no longer available",
            code="source_missing",
        )
    live = await session.execute(
        select(func.count())
        .select_from(ChunkRow)
        .where(ChunkRow.doc_id == document_id, ChunkRow.status == "active")
    )

    doc.parse_status = "pending"
    doc.parse_error = None
    job = await submit_job(
        job_type=JOB_TYPE,
        kb_id=doc.kb_id,
        source_id=doc.source_id,
        params={"document_id": str(doc.id)},
        created_by=user.id,
    )
    doc.meta = {**(doc.meta or {}), "ingest_job_id": str(job.id)}
    await session.commit()
    background.add_task(execute_job, job.id)
    log.info("document_reingest", document_id=str(doc.id), job_id=str(job.id))
    return ReingestSubmitted(
        document_id=doc.id, job_id=job.id, live_chunks=int(live.scalar_one())
    )


async def _chunk_or_404(session: SessionDep, chunk_id: uuid.UUID) -> ChunkRow:
    row = await session.get(ChunkRow, chunk_id)
    if row is None:
        raise NotFoundError("Chunk not found", code="chunk_not_found")
    return row


# ─── 检索自检 ─────────────────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResult)
async def search(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, description="Question in natural language")],
    kb_id: uuid.UUID | None = None,
) -> SearchResult:
    """跑一次真实的混合检索,把两条腿的名次与重排分原样返回。

    给**检索调试台**与 `make smoke-s2` 用 —— 问答链路走 `core/chat.py`,不走这里,
    但两边调的是同一个 `retriever.retrieve()`,所以这里看到的就是问答那一刻发生的事。
    """
    hits, trace = await retrieve(session, q, kb_ids=[kb_id] if kb_id else None)
    # guard 触发与否 Provider 只写了日志没往外返回(那是共享层,不在本域动)——
    # 但判据是纯函数的:策略是 guard 且最高分低于阈值,就是它退回了召回名次
    guard = (
        settings.doc_rag_rerank_strategy == "guard"
        and bool(hits)
        and max(h.score for h in hits) < settings.doc_rag_rerank_guard
    )
    return SearchResult(
        query=q,
        recall=SearchRecall(vector=trace.vector_hits, fts=trace.fts_hits, fused=trace.fused),
        reranked=trace.reranked,
        guard_fallback=guard,
        empty=not hits,
        hits=[
            SearchHit(
                chunk_id=h.chunk_id,
                document_id=h.doc_id,
                doc_name=h.doc_name,
                seq=h.seq,
                page_idx=h.page_idx,
                heading_path=h.heading_path or None,
                score=round(h.score, 4),
                rank_vector=h.rank_vector,
                rank_fts=h.rank_fts,
                figures=len(h.figures),
                content=h.content[:400],
            )
            for h in hits
        ],
    )
