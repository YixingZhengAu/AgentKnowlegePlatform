"""索引面维护:切片 → `chunks` 行 + 向量。

一条纪律和 S1 一样:**本文件不 commit**。发布是一个事务(写正式表 + 建索引),
提交由调用方统一做 —— 向量写失败时那些切片不该已经出现在正式表里。

`tsv` 是数据库的生成列(`to_tsvector('simple', content)`),**永远不要赋值**:
写 `content` 它自己就有了。
"""

import uuid

from sqlalchemy import cast, delete, func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Chunk as ChunkRow
from app.models import Document, MessageCitation
from app.providers import get_embedder
from app.schemas.document import Chunk
from app.services.document.chunker import count_tokens

log = get_logger(__name__)


def chunk_meta(chunk: Chunk) -> dict:
    """`chunks.meta` 的约定结构(DB-DESIGN §3)。

    图表的 `table_body` **不落库**:它是喂给模型的 OCR 提示,几 KB 的 HTML,
    留在 meta 里既没人读又把行撑大。原文线索留 caption/footnote 就够。
    """
    meta: dict = {"page_idx": chunk.page_idx}
    if chunk.bbox:
        meta["bbox"] = chunk.bbox
    if chunk.figures:
        meta["figures"] = [f.model_dump(exclude={"table_body"}) for f in chunk.figures]
    return meta


async def replace_document_chunks(
    session: AsyncSession, doc_id: uuid.UUID, chunks: list[Chunk]
) -> int:
    """重建某文档的切片行(含向量)。**不 commit。**

    重建而不是增量 diff:重新发布时切片的 seq 可能已经变了(合并过),
    对齐旧行的代价远高于重算一遍 embedding —— 而重算的钱由"只在发布时跑"兜住。

    🩸 **被引用过的旧行不删,退休成 `disabled`**(S2-4 分册 §4)。
    `message_citations.ref_id` 是弱引用(没有外键),删掉不会报错 ——
    只会让历史会话里那条引用点开变成"这条切片已不在库里"。
    退休而不是删,历史照样读得到,而 `status='disabled'` 让它从两条召回里消失。
    代价是 `(doc_id, seq)` 唯一约束:退休行占着老 seq,所以**必须先挪走再插新的** ——
    这里的做法是把退休行的 seq 置成负数(新行永远 ≥ 0),互不打架。

    Args:
        session: 调用方的事务。
        doc_id: 文档 id。
        chunks: 该文档**全部**要发布的切片(不是增量)。

    Returns:
        写入的行数。
    """
    await _retire_cited_then_delete_rest(session, doc_id)
    if not chunks:
        return 0

    vectors = await get_embedder().embed([c.embed_text for c in chunks])
    session.add_all(
        [
            ChunkRow(
                doc_id=doc_id,
                seq=c.seq,
                content=c.content,
                heading_path=c.heading_text or None,
                # 审核台改过正文之后 payload 里的 token_count 就旧了,落库前按最终正文重算
                token_count=count_tokens(c.content),
                embedding=vec,
                meta=chunk_meta(c),
            )
            for c, vec in zip(chunks, vectors, strict=True)
        ]
    )
    log.info("document_chunks_indexed", doc_id=str(doc_id), chunks=len(chunks))
    return len(chunks)


async def _retire_cited_then_delete_rest(session: AsyncSession, doc_id: uuid.UUID) -> None:
    """把被引用过的旧行退休,其余(**含用户手动禁用的**)一律删掉。

    退休 = `status='disabled'` + 清向量 + `meta.retired=true`。
    `seq` 原样保留 —— 唯一约束是**只管 active 行**的部分索引,所以退休行
    与新一代的同号行可以共存,不需要给 seq 编码。

    "其余一律删"包含上一代里被人手动禁用的行:它们也属于上一代,留着就是永远
    没人看得见、也永远不会被召回的幽灵行。
    """
    cited = select(MessageCitation.ref_id).where(MessageCitation.ref_id.is_not(None))
    retired = (
        await session.execute(
            update(ChunkRow)
            .where(ChunkRow.doc_id == doc_id, ChunkRow.id.in_(cited))
            .values(
                status="disabled",
                # 禁用即清向量:留着就是 HNSW 索引里一条永远召不回的死数据
                embedding=None,
                meta=ChunkRow.meta.op("||")(cast({"retired": True}, JSONB)),
            )
            .returning(ChunkRow.id)
        )
    ).all()
    await session.execute(
        delete(ChunkRow).where(ChunkRow.doc_id == doc_id, ChunkRow.id.not_in(cited))
    )
    if retired:
        log.info("document_chunks_retired", doc_id=str(doc_id), retired=len(retired))


async def drop_document_chunks(session: AsyncSession, doc_id: uuid.UUID) -> None:
    """删掉某文档的全部切片行。**不 commit。**"""
    await session.execute(delete(ChunkRow).where(ChunkRow.doc_id == doc_id))


async def chunk_count(session: AsyncSession, doc_id: uuid.UUID) -> int:
    """某文档**在用**的切片数(文档列表那一列)。

    只数 `active`:退休行(被引用过、重发布时留下的)不该让这个数字虚高。
    """
    stmt = (
        select(func.count())
        .select_from(ChunkRow)
        .where(ChunkRow.doc_id == doc_id, ChunkRow.status == "active")
    )
    return int((await session.execute(stmt)).scalar_one())


async def index_size(session: AsyncSession, kb_id: uuid.UUID | None = None) -> tuple[int, int]:
    """`(切片行数, 有向量的行数)` —— 冒烟脚本用它证明索引真的建起来了。"""
    stmt = select(func.count(ChunkRow.id), func.count(ChunkRow.embedding))
    if kb_id is not None:
        stmt = stmt.join(Document, Document.id == ChunkRow.doc_id).where(Document.kb_id == kb_id)
    total, vectored = (await session.execute(stmt)).one()
    return int(total), int(vectored)
