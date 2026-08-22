"""采纳即发布 —— 候选 QA(staging_items)→ 正式 QA(exact_qa_items + exact_qa_vectors)。

★ S1 的流程刻意比 DB-DESIGN 原本的"批量发布"语义更薄(S1-plan §4):
**没有目录前置、没有发布申请、没有审批、没有"待发布"中间态**。
点「采纳」的那一瞬间就写正式表 + 建向量索引,立刻参与检索。

于是 `ingest_jobs` 的状态机语义按 S1-plan §8.5 收窄:
`review` = "采纳进行中",全部候选都裁决完毕(没有 pending 了)才置 `published`,
它只作终态统计,漏斗数字记在 `publish_records.item_counts`。

**为什么保留通用 publisher 注册**(`@register_publisher("qa_pair")`):
`core/staging.py` 的批量发布骨架是 S0 定型的公共契约,S2/S3 都要用。
S1 自己走逐条采纳,但批量入口(`POST /api/jobs/{id}/publish`)也得能写正式表 ——
两条路复用同一个 `_publish_one()`,不会出现"批量发的那批没有向量"这种半残状态。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.logging import get_logger
from app.core.staging import assert_reviewable, count_by_status, register_publisher
from app.models import ExactQaItem, IngestJob, PublishRecord, StagingItem
from app.services.exact_qa.indexer import drop_item_vectors, rebuild_item_vectors

log = get_logger(__name__)

ITEM_TYPE = "qa_pair"


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- 写正式表


async def _publish_one(session: AsyncSession, staging: StagingItem) -> dict:
    """一条候选 → 一条正式 QA + 它的全部向量行。**不 commit**(采纳是一个事务)。

    幂等:已发布过的直接返回原来的 published_ref,不写第二份
    (前端重复点、批量与逐条撞在一起,都不该产生重复知识)。
    """
    if staging.published and staging.published_ref:
        return staging.published_ref

    payload = staging.payload or {}
    question = (payload.get("standard_question") or "").strip()
    answer = (payload.get("answer") or "").strip()
    if not question or not answer:
        # 抽取层已经保证非空,但人在审核台上可以改成空 —— 这里是最后一道防线
        raise ConflictError(
            "A verified answer needs both a question and an answer",
            code="qa_pair_incomplete",
        )

    item = ExactQaItem(
        kb_id=staging.kb_id,
        standard_question=question,
        answer=answer,
        similar_questions=list(payload.get("similar_questions") or []),
        keywords=list(payload.get("keywords") or []),
        source_staging_id=staging.id,
    )
    session.add(item)
    await session.flush()  # 要 item.id 才能建向量行
    faces = await rebuild_item_vectors(session, item)

    staging.published = True
    staging.published_ref = {
        "table": "exact_qa_items",
        "id": str(item.id),
        "index_faces": faces,
    }
    return staging.published_ref


@register_publisher(ITEM_TYPE)
async def publish_qa_pairs(
    session: AsyncSession, items: list[StagingItem]
) -> list[dict | None]:
    """批量发布入口(`core/staging.py::publish_job` 调它)。逐条走同一条路。"""
    refs: list[dict | None] = []
    for staging in items:
        refs.append(await _publish_one(session, staging))
    log.info("exact_qa_published_batch", count=len(items))
    return refs


# ---------------------------------------------------------------- 逐条采纳/不采纳


async def _pending_count(session: AsyncSession, job_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(StagingItem)
            .where(StagingItem.job_id == job_id, StagingItem.review_status == "pending")
        )
    ).scalar_one()


async def _finalize_if_done(session: AsyncSession, job: IngestJob) -> bool:
    """全部候选都裁决完 → job 置 published 并留一条审计记录。返回是否收尾了。

    这是"逐条采纳"语义下 job 的终态:它不再表示"批量发布动作发生过",
    只表示"这批候选人已经看完了"。漏斗数字(抽了几条、采纳几条)记在 item_counts。
    """
    if job.status != "review" or await _pending_count(session, job.id) > 0:
        return False

    items = (
        (await session.execute(select(StagingItem).where(StagingItem.job_id == job.id)))
        .scalars()
        .all()
    )
    counts = count_by_status([i.review_status for i in items])
    published = sum(1 for i in items if i.published)
    session.add(
        PublishRecord(
            job_id=job.id,
            kb_id=job.kb_id,
            item_counts={**counts, "published": published},
            published_by=None,
        )
    )
    job.status = "published"
    job.finished_at = _now()
    job.stats = {**job.stats, "published": published}
    log.info("exact_qa_job_finalized", job_id=str(job.id), published=published, counts=counts)
    return True


async def accept_candidate(
    session: AsyncSession, staging: StagingItem, *, user_id: uuid.UUID | None
) -> StagingItem:
    """★ 采纳 = 发布。一个事务里做完:写正式表 → 建向量索引 → 标记候选已发布。

    事务边界很重要:向量建失败时那条 QA 不该已经出现在正式表里
    (那会变成一条"永远命不中的知识",在界面上完全看不出来)。
    """
    if staging.published:
        raise ConflictError(
            "This candidate has already been accepted", code="item_already_published"
        )
    if staging.item_type != ITEM_TYPE:
        raise ConflictError(
            f"Not a QA candidate (item_type={staging.item_type})", code="item_type_mismatch"
        )
    job = await assert_reviewable(session, staging.job_id)

    ref = await _publish_one(session, staging)
    # 人工改过的痕迹要留住:modified 也是"通过"的一种(见 core/staging.py)
    if staging.review_status != "modified":
        staging.review_status = "approved"
    staging.reviewed_by, staging.reviewed_at = user_id, _now()
    await _finalize_if_done(session, job)
    await session.commit()
    await session.refresh(staging)
    log.info("exact_qa_accepted", staging_id=str(staging.id), published_ref=ref)
    return staging


async def reject_candidate(
    session: AsyncSession, staging: StagingItem, *, note: str, user_id: uuid.UUID | None
) -> StagingItem:
    """不采纳:留痕不入库。**理由必填** —— 它是下一轮调 prompt 的原始素材。"""
    if staging.published:
        raise ConflictError(
            "This candidate is already published; take it offline instead",
            code="item_already_published",
        )
    if not note.strip():
        raise ConflictError("A rejection needs a reason", code="reject_note_required")
    job = await assert_reviewable(session, staging.job_id)

    staging.review_status = "rejected"
    staging.review_note = note.strip()
    staging.reviewed_by, staging.reviewed_at = user_id, _now()
    await _finalize_if_done(session, job)
    await session.commit()
    await session.refresh(staging)
    log.info("exact_qa_rejected", staging_id=str(staging.id))
    return staging


# ---------------------------------------------------------------- 下线


async def disable_item(session: AsyncSession, item: ExactQaItem) -> ExactQaItem:
    """下线一条正式 QA:置 disabled + 删向量行,立刻不再被检索到。

    正式行留着(不物理删):它被 `message_citations.ref_id` 引用过,
    删掉的话历史消息里的引用会变成悬空。
    """
    item.status = "disabled"
    await drop_item_vectors(session, item.id)
    await session.commit()
    await session.refresh(item)
    log.info("exact_qa_disabled", item_id=str(item.id))
    return item
