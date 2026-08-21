"""摄取 Job 接口:提交 / 查进度 / 从失败步骤重跑。

派发用 **FastAPI BackgroundTasks**(刻意不上 Celery,S0 边界纪律):
响应发出去之后才开始跑,所以提交接口是瞬时返回的,进度靠前端轮询这里的 GET。

代价说清楚:进程重启 = 任务丢失。这不是漏洞而是取舍 ——
补偿手段是启动时的 `reap_abandoned_jobs()`(僵尸判失败)+ 心跳超时的惰性判定,
两者合起来保证"任务不会永远停在 running"。
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import NotFoundError
from app.core.jobs import execute_job, fail_if_stalled, known_job_types, retry_job, submit_job
from app.core.staging import publish_job

# 注册表靠 import 副作用填充:这一行没有,`demo_sleep` 就不存在。
# S1–S3 的 Job 子类同样要在这里(或 services 的 __init__)被 import 一次。
from app.core import jobs_demo  # noqa: F401  isort:skip
from app.models import IngestJob, KnowledgeBase
from app.schemas.common import ListResponse
from app.schemas.job import JobOut, JobSubmitRequest
from app.schemas.staging import PublishResult

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=ListResponse[JobOut])
async def list_jobs(
    session: SessionDep,
    kb_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> ListResponse:
    stmt = select(IngestJob).order_by(IngestJob.created_at.desc()).limit(limit)
    if kb_id is not None:
        stmt = stmt.where(IngestJob.kb_id == kb_id)
    if status is not None:
        stmt = stmt.where(IngestJob.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    items = [JobOut.model_validate(r) for r in rows]
    return ListResponse[JobOut](items=items, total=len(items))


@router.get("/types", response_model=list[str])
async def list_job_types() -> list[str]:
    """已注册的 job_type(前端"跑一个任务"的下拉框用它,不硬编码)。"""
    return known_job_types()


@router.post("", response_model=JobOut, status_code=201)
async def create_job(
    req: JobSubmitRequest,
    session: SessionDep,
    user: CurrentUser,
    background: BackgroundTasks,
) -> JobOut:
    # KB 不存在就直接 404:不拦的话会撞外键报成 db_error 503,掩盖真实原因
    if await session.get(KnowledgeBase, req.kb_id) is None:
        raise NotFoundError(f"Knowledge base {req.kb_id} not found")
    job = await submit_job(
        job_type=req.job_type,
        kb_id=req.kb_id,
        source_id=req.source_id,
        params=req.params,
        created_by=user.id,
    )
    background.add_task(execute_job, job.id)
    return JobOut.model_validate(job)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, session: SessionDep) -> JobOut:
    job = await session.get(IngestJob, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    # 惰性僵尸判定:心跳停了太久的 running 任务在这里被判失败
    job = await fail_if_stalled(job, session)
    return JobOut.model_validate(job)


@router.post("/{job_id}/retry", response_model=JobOut)
async def retry(job_id: uuid.UUID, background: BackgroundTasks) -> JobOut:
    """从失败的那一步重跑(前面已成功的步骤不重做)。"""
    job, from_step = await retry_job(job_id)
    background.add_task(execute_job, job.id, from_step=from_step)
    return JobOut.model_validate(job)


@router.post("/{job_id}/publish", response_model=PublishResult)
async def publish(job_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> PublishResult:
    """发布审核结果:approved/modified 的条目标记 published + 写一条 publish_records。

    S0 只做这层通用骨架 —— "写进正式表 + 建索引"由各类型的 publisher 在 S1–S3 插进来
    (`core/staging.py::register_publisher`),所以现在 `published_ref` 是 null。
    发布是 job 级动作(不是 item 级),所以路由挂在 jobs 下。
    """
    job, record = await publish_job(session, job_id, user_id=user.id)
    return PublishResult(
        record_id=record.id,
        job_id=job.id,
        job_status=job.status,
        published=int(record.item_counts.get("published", 0)),
        item_counts=record.item_counts,
        created_at=record.created_at,
    )
