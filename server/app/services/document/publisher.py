"""发布:审核通过的切片 → `chunks` 表 + 向量(一个事务)。

发布语义是 **S0 默认的批量发布**(S2-PRD D7):审核台里逐条编辑/不采纳,
最后按一次 Publish 全量落库 —— 与 S1 的"采纳即发布"不同,因为切片是**成套**的:
一份文档的切片彼此有 seq 上下文关系,一条一条地发布没有意义。

🩸 **一份文档 = 一次全删重建**,而不是"把这批新的插进去":
`core/staging.py` 只把**这一轮**新通过的候选交给 publisher(`not i.published`),
照着它给的那批做全删重建,会把上一轮已发布的切片一起抹掉。
所以这里自己回查该文档**全部**通过审核的候选,再整体重建 —— 重复发布因此是安全的。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.logging import get_logger
from app.core.staging import PUBLISHABLE_STATUSES, register_publisher
from app.models import StagingItem
from app.schemas.document import ITEM_TYPE, Chunk
from app.services.document.indexer import replace_document_chunks

log = get_logger(__name__)


def _document_id_of(item: StagingItem) -> uuid.UUID:
    """从 `origin_ref` 取文档 id。

    Raises:
        ConflictError: 候选没带来源(理论上不会发生,发生了就是摄取写坏了)。
    """
    raw = (item.origin_ref or {}).get("document_id")
    if not raw:
        raise ConflictError(
            "This chunk has no source document and cannot be published",
            code="chunk_origin_missing",
        )
    return uuid.UUID(str(raw))


async def _approved_of_document(
    session: AsyncSession, job_ids: set[uuid.UUID], doc_id: uuid.UUID
) -> list[StagingItem]:
    """该文档在这些 job 里**全部**通过审核的候选(含上一轮已发布的)。"""
    stmt = select(StagingItem).where(
        StagingItem.job_id.in_(job_ids),
        StagingItem.item_type == ITEM_TYPE,
        StagingItem.review_status.in_(PUBLISHABLE_STATUSES),
    )
    items = (await session.execute(stmt)).scalars().all()
    return [i for i in items if _document_id_of(i) == doc_id]


@register_publisher(ITEM_TYPE)
async def publish_chunks(session: AsyncSession, items: list[StagingItem]) -> list[dict | None]:
    """把审核通过的切片写进 `chunks`。**不 commit**(调用方统一提交)。

    Args:
        session: 调用方的事务。
        items: 本轮新通过审核、尚未发布的候选。

    Returns:
        与 `items` 同序的 `published_ref` 列表。
    """
    job_ids = {i.job_id for i in items}
    doc_ids = {_document_id_of(i) for i in items}

    refs: dict[uuid.UUID, dict] = {}
    for doc_id in doc_ids:
        approved = await _approved_of_document(session, job_ids, doc_id)
        chunks = sorted(
            (Chunk.model_validate(i.payload or {}) for i in approved), key=lambda c: c.seq
        )
        await replace_document_chunks(session, doc_id, chunks)
        for item in approved:
            refs[item.id] = {
                "table": "chunks",
                "doc_id": str(doc_id),
                "seq": (item.payload or {}).get("seq"),
            }

    log.info("document_published_batch", documents=len(doc_ids), chunks=len(items))
    return [refs.get(item.id) for item in items]
