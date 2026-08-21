"""待审内容的通用审核与发布骨架(S0-PLAN Step 8)。

**这一层为什么是通用的**:S1 抽 QA、S2 切文档、S3 同步 schema,产出的东西完全不同,
但"人过一眼 → 通过/驳回/改一改 → 点发布 → 留一条审计"这套流程一模一样。
所以审核与发布的**流程**在这里写一遍,各类知识只贡献两样东西:
前端的渲染器(`itemRenderer` / `editorRenderer`)与后端的 publisher(见下)。

**S0 刻意只做骨架**:发布 = 把 approved/modified 的条目标记 `published` + 写一条
`publish_records`。"写进正式表 + 建向量索引"是各类型自己的事,靠 `register_publisher()`
在 S1–S3 插进来 —— 所以现在没有任何 publisher 注册,发布后 `published_ref` 是 null,
这不是漏了,是这一层不该知道 `exact_qa_items` 长什么样。
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import IngestJob, PublishRecord, StagingItem
from app.models.ingest import REVIEW_STATUSES

log = get_logger(__name__)

# 会被发布的审核状态:approved(原样通过)与 modified(人工改过再通过)
PUBLISHABLE_STATUSES = ("approved", "modified")

# 允许人工设置的审核状态(pending 是初始值,不允许"退回待审"以外的花样;
# modified 由 PATCH 带 payload 时自动推导,不需要前端自己传)
REVIEWABLE_STATUSES = ("pending", "approved", "rejected", "modified")


# ---------------------------------------------------------------- 纯函数(可离线测)


def merge_payload(old: dict, patch: dict) -> dict:
    """payload 的 PATCH 语义:**顶层键浅合并**。

    为什么不整体替换:编辑器只改了 answer 时,没必要把整个 payload 回传一遍;
    为什么不深合并:payload 里的 list(similar_questions / keywords)是"整份重写"的语义,
    深合并会让"删掉一个相似问"变成不可能表达的操作。
    """
    return {**old, **patch}


def derive_review_status(*, requested: str | None, has_payload_edit: bool, current: str) -> str:
    """审核状态的推导规则(只有一处出处,前端不用重复这套逻辑)。

    - 前端显式传了状态 → 听它的(点"通过"就是 approved,即使同时改了内容)
    - 只改了内容没表态 → `modified`("改过了,算通过的一种")
    - 什么都没传 → 保持原状
    """
    if requested is not None:
        return requested
    if has_payload_edit:
        return "modified"
    return current


def count_by_status(statuses: list[str]) -> dict[str, int]:
    """审核状态计数(审核台顶部的筛选计数、publish_records.item_counts 都用它)。"""
    counts = {s: 0 for s in REVIEW_STATUSES}
    for s in statuses:
        if s in counts:
            counts[s] += 1
    return counts


# ---------------------------------------------------------------- publisher 注册表

# item_type -> 真正写正式表的函数。S1–S3 各注册一个,S0 是空的。
Publisher = Callable[[AsyncSession, list[StagingItem]], Awaitable[list[dict | None]]]
_PUBLISHERS: dict[str, Publisher] = {}


def register_publisher(item_type: str) -> Callable[[Publisher], Publisher]:
    """装饰器:给某个 item_type 登记 publisher(S1 写 exact_qa_items 时用)。"""

    def deco(fn: Publisher) -> Publisher:
        _PUBLISHERS[item_type] = fn
        return fn

    return deco


def known_publishers() -> list[str]:
    return sorted(_PUBLISHERS)


# ---------------------------------------------------------------- DB 操作


def _now() -> datetime:
    return datetime.now(UTC)


async def assert_reviewable(session: AsyncSession, job_id: uuid.UUID) -> IngestJob:
    """审核动作的前置检查:只有停在 `review` 的 job 才允许审。

    为什么必须在后端拦:发布之后再"通过"一条,那条永远发不出去(job 已是 published,
    发布接口不会再受理)—— 界面上的只读是提示,这里才是防线。
    """
    job = await session.get(IngestJob, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    if job.status != "review":
        raise ConflictError(
            f"Job is '{job.status}', items can only be reviewed while it waits for review",
            code="job_not_reviewable",
        )
    return job


async def get_item(session: AsyncSession, item_id: uuid.UUID) -> StagingItem:
    item = await session.get(StagingItem, item_id)
    if item is None:
        raise NotFoundError(f"Staging item {item_id} not found")
    return item


async def patch_item(
    session: AsyncSession,
    item: StagingItem,
    *,
    payload: dict | None,
    review_status: str | None,
    review_note: str | None,
    user_id: uuid.UUID | None,
) -> StagingItem:
    """审一条:改内容 / 改状态 / 加备注。已发布的条目不允许再改。"""
    if item.published:
        raise ConflictError(
            "This item is already published and cannot be edited",
            code="item_already_published",
        )
    await assert_reviewable(session, item.job_id)
    if payload:
        # jsonb 列必须整体重新赋值:就地改 dict,SQLAlchemy 检测不到变更
        item.payload = merge_payload(item.payload, payload)
    status = derive_review_status(
        requested=review_status, has_payload_edit=bool(payload), current=item.review_status
    )
    if status != item.review_status:
        item.review_status = status
    if review_note is not None:
        item.review_note = review_note
    # 审核痕迹:谁、什么时候。pending(退回待审)时清掉,不留假痕迹
    if item.review_status == "pending":
        item.reviewed_by, item.reviewed_at = None, None
    else:
        item.reviewed_by, item.reviewed_at = user_id, _now()
    await session.commit()
    await session.refresh(item)
    return item


async def bulk_review(
    session: AsyncSession,
    *,
    ids: list[uuid.UUID],
    review_status: str,
    user_id: uuid.UUID | None,
) -> int:
    """批量通过/驳回。已发布的条目静默跳过(不让一条已发布的把整批操作打断)。"""
    rows = (
        (await session.execute(select(StagingItem).where(StagingItem.id.in_(ids)))).scalars().all()
    )
    # 批量也要过同一道闸(取第一条的 job:一次批量操作必然来自同一个审核页)
    if rows:
        await assert_reviewable(session, rows[0].job_id)
    touched = 0
    for item in rows:
        if item.published:
            continue
        item.review_status = review_status
        if review_status == "pending":
            item.reviewed_by, item.reviewed_at = None, None
        else:
            item.reviewed_by, item.reviewed_at = user_id, _now()
        touched += 1
    await session.commit()
    log.info("staging_bulk_review", status=review_status, requested=len(ids), updated=touched)
    return touched


async def summarize(session: AsyncSession, job_id: uuid.UUID) -> dict[str, Any]:
    """一个 job 下待审内容的计数(审核台顶部的筛选标签直接渲染它)。"""
    rows = (
        await session.execute(
            select(StagingItem.review_status, func.count())
            .where(StagingItem.job_id == job_id)
            .group_by(StagingItem.review_status)
        )
    ).all()
    counts = {s: 0 for s in REVIEW_STATUSES}
    for status, n in rows:
        counts[status] = n
    published = (
        await session.execute(
            select(func.count())
            .select_from(StagingItem)
            .where(StagingItem.job_id == job_id, StagingItem.published.is_(True))
        )
    ).scalar_one()
    return {**counts, "total": sum(counts.values()), "published": published}


async def publish_job(
    session: AsyncSession, job_id: uuid.UUID, *, user_id: uuid.UUID | None
) -> tuple[IngestJob, PublishRecord]:
    """发布一个 job 的审核结果。

    只有 `review` 状态的 job 能发布(发过一次就是 `published`,再点会 409 —— 这就是
    "重复点发布"的防线,不靠前端禁用按钮)。
    """
    job = await session.get(IngestJob, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    if job.status != "review":
        raise ConflictError(
            f"Job is '{job.status}', only jobs waiting for review can be published",
            code="job_not_publishable",
        )

    items = (
        (await session.execute(select(StagingItem).where(StagingItem.job_id == job_id)))
        .scalars()
        .all()
    )
    counts = count_by_status([i.review_status for i in items])
    to_publish = [i for i in items if i.review_status in PUBLISHABLE_STATUSES and not i.published]
    if not to_publish:
        raise ConflictError(
            "Nothing to publish: approve at least one item first",
            code="nothing_to_publish",
        )

    # publishing 是个瞬时中间态,但要落库:发布真的写正式表时(S1 起)可能耗时,
    # 状态机上必须有一格表示"正在发",否则失败时不知道停在哪
    job.status = "publishing"
    await session.commit()

    # 按 item_type 分组交给各自的 publisher。S0 没有注册任何 publisher,
    # 于是只做通用部分(标记 published),published_ref 留空。
    for item_type in {i.item_type for i in to_publish}:
        group = [i for i in to_publish if i.item_type == item_type]
        publisher = _PUBLISHERS.get(item_type)
        if publisher is None:
            log.info("publisher_missing", item_type=item_type, count=len(group))
            continue
        refs = await publisher(session, group)
        for item, ref in zip(group, refs, strict=True):
            item.published_ref = ref

    now = _now()
    for item in to_publish:
        item.published = True

    record = PublishRecord(
        job_id=job.id,
        kb_id=job.kb_id,
        item_counts={**counts, "published": len(to_publish)},
        published_by=user_id,
    )
    session.add(record)
    job.status = "published"
    job.finished_at = now
    job.stats = {**job.stats, "published": len(to_publish)}
    await session.commit()
    await session.refresh(record)
    await session.refresh(job)
    log.info("job_published", job_id=str(job.id), published=len(to_publish), counts=counts)
    return job, record
