"""精准问答(S1)的 REST 接口:上传 → 校对 → 确认抽取 → 采纳 → 正式 QA 管理。

**候选 QA 的列表与编辑不在这里** —— 它们走 S0 的通用审核接口
(`GET /api/staging?job_id=`、`PATCH /api/staging/{id}`),因为"筛选/编辑/批量"
对三类知识是同一套流程。本文件只放 S1 独有的那几个动作:

| 动作 | 端点 | 为什么不能通用化 |
| --- | --- | --- |
| 上传 PDF 并启动解析 | `POST /api/exact-qa/documents` | 建 source+document+job 是本域的三件事 |
| 读/写校对文本 | `GET|PUT .../documents/{id}/review-text` | 只有本域有"校对解析文本"这道人工关 |
| 确认开始抽取 | `POST .../documents/{id}/confirm-extract` | 两个 Job 之间的人工衔接点 |
| 采纳 / 不采纳 | `POST .../candidates/{id}/accept|reject` | **采纳即发布**(写正式表+建向量) |
| 正式 QA 管理 | `GET .../items`、`POST .../items/{id}/disable` | 正式表是本域私有的 |
| 删除文档 | `DELETE .../documents/{id}` | 要一起清掉解析产物与两个 Job |

图片出口在 `api/files.py`。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Query, UploadFile
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import ConflictError, NotFoundError
from app.core.jobs import execute_job, submit_job
from app.core.logging import get_logger
from app.core.staging import get_item
from app.models import (
    Document,
    ExactQaItem,
    ExactQaVector,
    IngestJob,
    IngestSource,
    KnowledgeBase,
    StagingItem,
)
from app.schemas.common import ListResponse
from app.schemas.exact_qa import (
    REVIEWED_MD_NAME,
    ConfirmExtractResult,
    DocumentFunnel,
    DocumentOut,
    ExactQaItemDetail,
    ExactQaItemOut,
    OriginRef,
    ParseStats,
    RejectRequest,
    ReviewTextOut,
    ReviewTextUpdate,
    UploadResult,
)
from app.schemas.staging import StagingItemOut
from app.services.exact_qa import storage
from app.services.exact_qa.publisher import accept_candidate, disable_item, reject_candidate

router = APIRouter(prefix="/api/exact-qa", tags=["exact_qa"])
log = get_logger(__name__)

#: S1 只支持 PDF(PRD 的边界),别的类型直接拒,不要"先收下再失败"
ALLOWED_MIME = ("application/pdf",)
MAX_UPLOAD_MB = 50


# ---------------------------------------------------------------- 文档


async def _get_document(session: SessionDep, document_id: uuid.UUID) -> Document:
    doc = await session.get(Document, document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    return doc


async def _funnel(session: SessionDep, extract_job_id: uuid.UUID | None) -> DocumentFunnel:
    """漏斗计数按 review_status 分组数一次,不在前端数(前端只拿到当前页)。"""
    if extract_job_id is None:
        return DocumentFunnel()
    rows = (
        await session.execute(
            select(StagingItem.review_status, func.count())
            .where(StagingItem.job_id == extract_job_id)
            .group_by(StagingItem.review_status)
        )
    ).all()
    counts = dict(rows)
    return DocumentFunnel(
        candidates=sum(counts.values()),
        pending=counts.get("pending", 0),
        # approved 与 modified 都是"通过"(modified = 人工改过再通过)
        accepted=counts.get("approved", 0) + counts.get("modified", 0),
        rejected=counts.get("rejected", 0),
    )


def _stage(doc: Document, extract_job: IngestJob | None, funnel: DocumentFunnel) -> str:
    """界面用的推导态。文档表只存解析态,别的从 Job 状态推(S1-plan §8.4)。"""
    if doc.parse_status in ("pending", "parsing"):
        return doc.parse_status
    if doc.parse_status == "failed":
        return "failed"
    if extract_job is None:
        return "review_text"  # 解析完了,等人校对
    if extract_job.status in ("queued", "running"):
        return "extracting"
    if extract_job.status == "failed":
        return "extract_failed"
    if funnel.pending > 0:
        return "review_qa"  # 候选在等人采纳
    return "done"


async def _document_out(session: SessionDep, doc: Document) -> DocumentOut:
    meta = doc.meta or {}
    extract_job_id = meta.get("extract_job_id")
    extract_job = (
        await session.get(IngestJob, uuid.UUID(extract_job_id)) if extract_job_id else None
    )
    funnel = await _funnel(session, extract_job.id if extract_job else None)
    stats = meta.get("parse_stats")
    return DocumentOut(
        id=doc.id,
        kb_id=doc.kb_id,
        name=doc.name,
        file_type=doc.file_type,
        size_bytes=doc.size_bytes,
        parse_status=doc.parse_status,
        parse_error=doc.parse_error,
        stage=_stage(doc, extract_job, funnel),
        parse_job_id=uuid.UUID(meta["parse_job_id"]) if meta.get("parse_job_id") else None,
        extract_job_id=extract_job.id if extract_job else None,
        parse_stats=ParseStats.model_validate(stats) if stats else None,
        funnel=funnel,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


async def _default_kb(session: SessionDep) -> KnowledgeBase:
    kb = (
        await session.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.type == "exact_qa", KnowledgeBase.status == "active")
            .order_by(KnowledgeBase.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()
    if kb is None:
        raise NotFoundError(
            "No exact_qa knowledge base found, run `make seed`", code="kb_missing"
        )
    return kb


@router.post("/documents", response_model=UploadResult, status_code=201)
async def upload_document(
    session: SessionDep,
    user: CurrentUser,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File(description="PDF only (S1 boundary)")],
    kb_id: uuid.UUID | None = None,
) -> UploadResult:
    """上传 PDF → 建 source + document → **立刻派发解析 Job**。

    一次请求做完三件事而不是让前端分三步:上传后必然要解析,拆开只会多两个来回,
    而且中间任何一步失败都会留下孤儿数据。
    """
    if file.content_type not in ALLOWED_MIME:
        raise ConflictError(
            f"S1 only accepts PDF (got {file.content_type})", code="unsupported_file_type"
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
    await session.flush()
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
        job_type="qa_parse",
        kb_id=kb.id,
        source_id=source.id,
        params={"document_id": str(doc.id)},
        created_by=user.id,
    )
    doc.meta = {**(doc.meta or {}), "parse_job_id": str(job.id)}
    await session.commit()
    background.add_task(execute_job, job.id)
    log.info("exact_qa_uploaded", document_id=str(doc.id), job_id=str(job.id), bytes=len(data))
    return UploadResult(document_id=doc.id, source_id=source.id, job_id=job.id)


@router.get("/documents", response_model=ListResponse[DocumentOut])
async def list_documents(
    session: SessionDep,
    kb_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> ListResponse:
    stmt = select(Document)
    if kb_id is not None:
        stmt = stmt.where(Document.kb_id == kb_id)
    else:
        stmt = stmt.where(Document.kb_id == (await _default_kb(session)).id)
    # total 是**过滤后的总数**,不是本页条数 —— 否则前端一到 limit 就把总数显示成 limit
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(
        stmt.order_by(Document.created_at.desc()).limit(limit))).scalars().all()
    items = [await _document_out(session, d) for d in rows]
    return ListResponse[DocumentOut](items=items, total=total)


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: uuid.UUID, session: SessionDep) -> DocumentOut:
    return await _document_out(session, await _get_document(session, document_id))


# ---------------------------------------------------------------- 校对文本


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, session: SessionDep) -> None:
    """删掉一份文档:两个 Job(级联带走候选)、文档行、上传原件、解析产物目录。

    **有已发布问答的文档不许删**(409):正式 QA 的出处存在候选行的 `origin_ref` 里
    (`exact_qa_items.source_staging_id` 指过去),删了文档,引用里"跳到第 N 页"就悬空了。
    要清掉这类文档,先把它的正式 QA 逐条下线 —— 那是个显式动作,不该由删文档顺手替人做。

    这是给演示现场准备的:传错文件、解析失败的文档能自己清掉,不用去翻数据库。
    """
    doc = await _get_document(session, document_id)
    meta = doc.meta or {}
    job_ids = [
        uuid.UUID(meta[k]) for k in ("parse_job_id", "extract_job_id") if meta.get(k)
    ]
    if job_ids:
        published = (
            await session.execute(
                select(func.count())
                .select_from(StagingItem)
                .where(StagingItem.job_id.in_(job_ids), StagingItem.published.is_(True))
            )
        ).scalar_one()
        if published:
            raise ConflictError(
                f"This document has {published} published Q&A item(s); disable them first",
                code="document_has_published_qa",
            )

    source_id = doc.source_id
    await session.delete(doc)  # chunks 级联;candidates 随 job 级联(下一句)
    for job_id in job_ids:
        job = await session.get(IngestJob, job_id)
        if job is not None:
            await session.delete(job)
    if source_id is not None:
        src = await session.get(IngestSource, source_id)
        if src is not None:
            await session.delete(src)
    await session.commit()
    # 文件最后删:库里事务成了才动磁盘,反过来会出现"文件没了但行还在"
    storage.remove_document_files(str(document_id), doc.raw_uri)
    log.info("exact_qa_document_deleted", document_id=str(document_id), jobs=len(job_ids))


@router.get("/documents/{document_id}/review-text", response_model=ReviewTextOut)
async def get_review_text(document_id: uuid.UUID, session: SessionDep) -> ReviewTextOut:
    """校对页的数据源。**图片路径在这里改写成文件服务 URL**(入库仍是相对路径)。"""
    doc = await _get_document(session, document_id)
    if doc.parse_status != "parsed":
        raise ConflictError(
            f"Document is '{doc.parse_status}', there is no parsed text to review yet",
            code="not_parsed",
        )
    source, text = storage.source_md(str(document_id))
    result = storage.load_parse_result(str(document_id))
    return ReviewTextOut(
        document_id=document_id,
        source=source,
        text=storage.rewrite_image_urls(text, str(document_id)),
        pages=result.pages,
        images=result.images,
        reviewed=source == REVIEWED_MD_NAME,
    )


@router.put("/documents/{document_id}/review-text", response_model=ReviewTextOut)
async def save_review_text(
    document_id: uuid.UUID, req: ReviewTextUpdate, session: SessionDep
) -> ReviewTextOut:
    """保存校对结果到 reviewed.md。抽取用的就是这一份(没有它才退回 paged.md)。"""
    doc = await _get_document(session, document_id)
    if doc.parse_status != "parsed":
        raise ConflictError(f"Document is '{doc.parse_status}'", code="not_parsed")
    storage.save_reviewed_md(str(document_id), req.text)
    doc.meta = {**(doc.meta or {}), "review_source": REVIEWED_MD_NAME}
    await session.commit()
    return await get_review_text(document_id, session)


@router.post("/documents/{document_id}/confirm-extract", response_model=ConfirmExtractResult)
async def confirm_extract(
    document_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    background: BackgroundTasks,
) -> ConfirmExtractResult:
    """第一道人工关的出口:「确认,开始抽取」。派发 qa_extract Job。"""
    doc = await _get_document(session, document_id)
    if doc.parse_status != "parsed":
        raise ConflictError(
            f"Document is '{doc.parse_status}', proofread the parsed text first",
            code="not_parsed",
        )
    meta = doc.meta or {}
    old = meta.get("extract_job_id")
    if old:
        old_job = await session.get(IngestJob, uuid.UUID(old))
        # 已经抽过一轮就不许再抽:否则同一份文档会出两批候选,采纳后成重复知识
        if old_job is not None and old_job.status != "failed":
            raise ConflictError(
                "Extraction already ran for this document; retry the job instead",
                code="already_extracted",
                detail={"job_id": old},
            )

    job = await submit_job(
        job_type="qa_extract",
        kb_id=doc.kb_id,
        source_id=doc.source_id,
        params={"document_id": str(doc.id)},
        created_by=user.id,
    )
    doc.meta = {**meta, "extract_job_id": str(job.id)}
    await session.commit()
    background.add_task(execute_job, job.id)
    return ConfirmExtractResult(job_id=job.id, document_id=doc.id)


# ---------------------------------------------------------------- 采纳 / 不采纳


@router.post("/candidates/{item_id}/accept", response_model=StagingItemOut)
async def accept(item_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> StagingItemOut:
    """★ 采纳即发布:一个事务里写 `exact_qa_items` + 建向量索引,立刻参与检索。"""
    item = await get_item(session, item_id)
    return StagingItemOut.model_validate(
        await accept_candidate(session, item, user_id=user.id)
    )


@router.post("/candidates/{item_id}/reject", response_model=StagingItemOut)
async def reject(
    item_id: uuid.UUID, req: RejectRequest, session: SessionDep, user: CurrentUser
) -> StagingItemOut:
    """不采纳:留痕不入库,理由必填。"""
    item = await get_item(session, item_id)
    return StagingItemOut.model_validate(
        await reject_candidate(session, item, note=req.note, user_id=user.id)
    )


# ---------------------------------------------------------------- 正式 QA


async def _face_counts(session: SessionDep, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not item_ids:
        return {}
    rows = (
        await session.execute(
            select(ExactQaVector.item_id, func.count())
            .where(ExactQaVector.item_id.in_(item_ids))
            .group_by(ExactQaVector.item_id)
        )
    ).all()
    return dict(rows)


@router.get("/items", response_model=ListResponse[ExactQaItemOut])
async def list_items(
    session: SessionDep,
    kb_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> ListResponse:
    """正式 QA 列表:**不带答案正文**(列表轻详情重),带索引面行数好确认它真的可被检索。"""
    stmt = select(ExactQaItem)
    if kb_id is not None:
        stmt = stmt.where(ExactQaItem.kb_id == kb_id)
    if status is not None:
        stmt = stmt.where(ExactQaItem.status == status)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(
        stmt.order_by(ExactQaItem.created_at.desc()).limit(limit))).scalars().all()
    faces = await _face_counts(session, [r.id for r in rows])
    items = [
        ExactQaItemOut(
            id=r.id,
            kb_id=r.kb_id,
            standard_question=r.standard_question,
            keywords=list(r.keywords or []),
            similar_count=len(r.similar_questions or []),
            status=r.status,
            index_faces=faces.get(r.id, 0),
            source_staging_id=r.source_staging_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
    return ListResponse[ExactQaItemOut](items=items, total=total)


@router.get("/items/{item_id}", response_model=ExactQaItemDetail)
async def get_item_detail(item_id: uuid.UUID, session: SessionDep) -> ExactQaItemDetail:
    item = await session.get(ExactQaItem, item_id)
    if item is None:
        raise NotFoundError(f"Exact QA item {item_id} not found")
    faces = await _face_counts(session, [item.id])
    origin = None
    if item.source_staging_id:
        staging = await session.get(StagingItem, item.source_staging_id)
        if staging is not None and staging.origin_ref:
            origin = OriginRef.model_validate(staging.origin_ref)
    return ExactQaItemDetail(
        id=item.id,
        kb_id=item.kb_id,
        standard_question=item.standard_question,
        answer=item.answer,
        similar_questions=list(item.similar_questions or []),
        keywords=list(item.keywords or []),
        similar_count=len(item.similar_questions or []),
        status=item.status,
        index_faces=faces.get(item.id, 0),
        source_staging_id=item.source_staging_id,
        origin_ref=origin,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post("/items/{item_id}/disable", response_model=ExactQaItemOut)
async def disable(item_id: uuid.UUID, session: SessionDep) -> ExactQaItemOut:
    """下线:置 disabled + 删向量行(正式行留着,历史消息里的引用不悬空)。"""
    item = await session.get(ExactQaItem, item_id)
    if item is None:
        raise NotFoundError(f"Exact QA item {item_id} not found")
    await disable_item(session, item)
    return ExactQaItemOut(
        id=item.id,
        kb_id=item.kb_id,
        standard_question=item.standard_question,
        keywords=list(item.keywords or []),
        similar_count=len(item.similar_questions or []),
        status=item.status,
        index_faces=0,
        source_staging_id=item.source_staging_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )
