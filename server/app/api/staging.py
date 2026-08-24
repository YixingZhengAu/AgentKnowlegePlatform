"""待审内容接口:列表 / 计数 / 审一条 / 批量审(S0-PLAN Step 8)。

发布接口在 `api/jobs.py`(`POST /api/jobs/{id}/publish`)—— 发布是**一个 job 的**动作,
不是某条 item 的动作,所以挂在 job 下面。

**为什么按 job_id 查而不是按 kb_id**:一次审核就是"审这一批加工产物"。
按 KB 查会把历史上所有批次混在一起,审到一半分不清哪条是这次抽出来的。
"""

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.staging import bulk_review, get_item, patch_item, summarize
from app.models import StagingItem
from app.schemas.common import ListResponse
from app.schemas.staging import (
    StagingBulkRequest,
    StagingBulkResult,
    StagingItemOut,
    StagingItemPatch,
    StagingSummary,
)

router = APIRouter(prefix="/api/staging", tags=["staging"])

# 排序键:审核台默认"最不靠谱的先看"(置信度升序)—— 人的时间花在最可能出错的地方
SORTS = {
    "confidence_asc": (StagingItem.confidence.asc().nullsfirst(), StagingItem.created_at.asc()),
    "confidence_desc": (StagingItem.confidence.desc().nullslast(), StagingItem.created_at.asc()),
    "created_asc": (StagingItem.created_at.asc(),),
    "created_desc": (StagingItem.created_at.desc(),),
}
# 锚定的正则:不加 ^$ 的话 "confidence_ascX" 也算合法,再去查 SORTS 会 KeyError 500
SORT_PATTERN = f"^({'|'.join(SORTS)})$"


@router.get("", response_model=ListResponse[StagingItemOut])
async def list_staging_items(
    session: SessionDep,
    job_id: uuid.UUID,
    review_status: str | None = None,
    item_type: str | None = None,
    sort: str = Query("confidence_asc", pattern=SORT_PATTERN),
    limit: int = Query(200, ge=1, le=500),
) -> ListResponse:
    stmt = select(StagingItem).where(StagingItem.job_id == job_id)
    if review_status is not None:
        stmt = stmt.where(StagingItem.review_status == review_status)
    if item_type is not None:
        stmt = stmt.where(StagingItem.item_type == item_type)
    # total 是过滤后的总数,不是本页条数(审核台一次能有几百条候选,很容易撞到 limit)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(
        stmt.order_by(*SORTS[sort]).limit(limit))).scalars().all()
    items = [StagingItemOut.model_validate(r) for r in rows]
    return ListResponse[StagingItemOut](items=items, total=total)


@router.get("/summary", response_model=StagingSummary)
async def staging_summary(session: SessionDep, job_id: uuid.UUID) -> StagingSummary:
    return StagingSummary(**await summarize(session, job_id))


@router.patch("/{item_id}", response_model=StagingItemOut)
async def patch_staging_item(
    item_id: uuid.UUID,
    req: StagingItemPatch,
    session: SessionDep,
    user: CurrentUser,
) -> StagingItemOut:
    item = await get_item(session, item_id)
    item = await patch_item(
        session,
        item,
        payload=req.payload,
        review_status=req.review_status,
        review_note=req.review_note,
        user_id=user.id,
    )
    return StagingItemOut.model_validate(item)


@router.post("/bulk", response_model=StagingBulkResult)
async def bulk_review_items(
    req: StagingBulkRequest,
    session: SessionDep,
    user: CurrentUser,
) -> StagingBulkResult:
    updated = await bulk_review(
        session, ids=req.ids, review_status=req.review_status, user_id=user.id
    )
    return StagingBulkResult(updated=updated)
