"""通用 Job 框架 —— 三类知识的摄取都靠它(S0-PLAN Step 7.2)。

**为什么值得单独做一层**:S1 抽 QA、S2 切文档、S3 同步 schema,三件事的业务完全不同,
但"分步执行 / 报进度 / 分步日志 / 失败可从该步重跑 / 前端一个进度条组件通吃"这套骨架完全一样。
S1–S3 只贡献一个子类,这份文件不用改。

子类要写的只有两样东西:

```python
class QaExtractJob(JobRunner):
    job_type = "qa_extract"
    steps = [JobStepDef("parse", "Parse source"), JobStepDef("extract", "Extract QA pairs")]

    async def step_parse(self, ctx: JobRunContext) -> str | None: ...
    async def step_extract(self, ctx: JobRunContext) -> str | None: ...
```

框架负责:状态机、`progress`、`step_logs`、异常落 `error`、心跳、从失败步骤重跑。

**三个刻意的设计决定**:

1. **步骤名是声明式的**(`steps` 是数据不是代码流程),所以前端在任务开始前就能画出
   全部步骤的骨架,而不是等日志一条条冒出来才知道有几步。
2. **每次写库都自己开一个短 session**。Job 是长任务(可能跑几分钟),
   不能借用请求作用域的 session —— 请求早就结束了。
3. **心跳 + 启动清理 = 没有僵尸任务**。进程内 BackgroundTasks 不可能跨重启存活,
   所以启动时凡是 `running` 的都是僵尸;进程活着但任务被取消的情况靠心跳超时兜住。
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import select, update

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models import IngestJob
from app.models.ingest import JOB_HEARTBEAT_TIMEOUT_SEC

log = get_logger(__name__)

# 心跳刷新间隔:必须显著小于 JOB_HEARTBEAT_TIMEOUT_SEC,否则正常跑的任务会被误判成僵尸
HEARTBEAT_INTERVAL_SEC = 15

# 被 detach 出去的后台任务:必须持引用,否则可能被 GC(asyncio 只持弱引用)
_BACKGROUND: set[asyncio.Task] = set()


def _detach(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)
    return task


@dataclass(frozen=True, slots=True)
class JobStepDef:
    """一个步骤的声明。`name` 同时是 `step_<name>` 方法名的后缀。"""

    name: str
    title: str


@dataclass(slots=True)
class JobRunContext:
    """交给步骤方法的上下文:任务标识 + 参数 + 一个跨步骤传值的暗兜。"""

    job_id: uuid.UUID
    kb_id: uuid.UUID
    source_id: uuid.UUID | None
    params: dict
    # 步骤之间传中间结果(parse 的产物给 extract 用),不落库
    scratch: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.scratch is None:
            self.scratch = {}


class JobRunner(ABC):
    """Job 执行器基类。子类声明 `job_type` / `steps`,并为每步实现 `step_<name>`。"""

    job_type: ClassVar[str]
    steps: ClassVar[list[JobStepDef]]
    # 全部步骤跑完后的落点。摄取类任务停在 review 等人审(Step 8 的审核台接手);
    # 不产出待审内容的任务可以覆盖成 "published"。
    terminal_status: ClassVar[str] = "review"

    @abstractmethod
    async def prepare(self, ctx: JobRunContext) -> None:
        """跑第一步之前的准备(重跑时也会执行,所以必须幂等)。"""

    async def run_step(self, step: JobStepDef, ctx: JobRunContext) -> str | None:
        """默认按约定分发到 `step_<name>`;返回值作为该步日志的 message。"""
        handler = getattr(self, f"step_{step.name}", None)
        if handler is None:
            raise NotImplementedError(f"{type(self).__name__} 缺少 step_{step.name}()")
        return await handler(ctx)


# ---------------------------------------------------------------- 注册表

_REGISTRY: dict[str, type[JobRunner]] = {}


def register_job(cls: type[JobRunner]) -> type[JobRunner]:
    """装饰器:把 Job 子类登记进注册表(job_type -> 类)。"""
    _REGISTRY[cls.job_type] = cls
    return cls


def get_runner_cls(job_type: str) -> type[JobRunner]:
    cls = _REGISTRY.get(job_type)
    if cls is None:
        raise NotFoundError(
            f"Unknown job type '{job_type}'",
            detail={"known": sorted(_REGISTRY)},
            code="unknown_job_type",
        )
    return cls


def known_job_types() -> list[str]:
    return sorted(_REGISTRY)


# ---------------------------------------------------------------- 落库小工具


def _now() -> datetime:
    return datetime.now(UTC)


async def _patch(job_id: uuid.UUID, **fields: Any) -> None:
    """给一行 job 打补丁。自己开 session:Job 是长任务,不能借请求作用域的 session。"""
    async with SessionLocal() as session:
        await session.execute(update(IngestJob).where(IngestJob.id == job_id).values(**fields))
        await session.commit()


async def _append_log(job_id: uuid.UUID, entry: dict) -> None:
    """追加一条分步日志。

    注意:JSONB 列里的 list 就地 append,SQLAlchemy 检测不到变更 —— 必须整体重新赋值。
    """
    async with SessionLocal() as session:
        job = await session.get(IngestJob, job_id)
        if job is None:
            return
        job.step_logs = [*job.step_logs, entry]
        await session.commit()


async def _heartbeat_loop(job_id: uuid.UUID) -> None:
    """任务跑着就定期盖时间戳。它是"进程活着但任务死了"这种情况的唯一线索。"""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
            await _patch(job_id, heartbeat_at=_now())
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # 心跳失败不该弄死任务本体
        log.warning("job_heartbeat_failed", job_id=str(job_id), error=str(exc))


# ---------------------------------------------------------------- 提交与执行


async def submit_job(
    *,
    job_type: str,
    kb_id: uuid.UUID,
    source_id: uuid.UUID | None = None,
    params: dict | None = None,
    created_by: uuid.UUID | None = None,
) -> IngestJob:
    """建一行 `ingest_jobs`(status=queued)并返回。**派发由调用方用 BackgroundTasks 做**。

    为什么分两步:先落库再派发,页面拿到 job_id 时任务一定已经存在,
    轮询 `GET /api/jobs/{id}` 不会撞到 404。
    """
    runner_cls = get_runner_cls(job_type)
    async with SessionLocal() as session:
        job = IngestJob(
            kb_id=kb_id,
            source_id=source_id,
            job_type=job_type,
            status="queued",
            # 步骤骨架现在就写进去:前端在任务真正开始前就能画出全部步骤
            steps=[{"name": s.name, "title": s.title} for s in runner_cls.steps],
            params=params or {},
            created_by=created_by,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
    log.info("job_submitted", job_id=str(job.id), job_type=job_type, steps=len(runner_cls.steps))
    return job


async def execute_job(job_id: uuid.UUID, *, from_step: str | None = None) -> None:
    """执行(或重跑)一个 job。**永远不抛异常**:失败写进 `error` 字段。

    `from_step` 不为空时,该步之前的步骤视为已完成(重跑不重做已成功的活)。
    """
    async with SessionLocal() as session:
        job = await session.get(IngestJob, job_id)
        if job is None:
            log.warning("job_missing_on_execute", job_id=str(job_id))
            return
        runner_cls = get_runner_cls(job.job_type)
        ctx = JobRunContext(
            job_id=job.id, kb_id=job.kb_id, source_id=job.source_id, params=dict(job.params)
        )
        steps = runner_cls.steps
        start_at = 0
        if from_step is not None:
            names = [s.name for s in steps]
            if from_step not in names:
                log.warning("job_retry_unknown_step", job_id=str(job_id), step=from_step)
                return
            start_at = names.index(from_step)

    runner = runner_cls()
    total = len(steps)
    heartbeat = _detach(_heartbeat_loop(job_id), name=f"job-heartbeat-{job_id}")

    await _patch(
        job_id,
        status="running",
        started_at=_now(),
        heartbeat_at=_now(),
        finished_at=None,
        error=None,
        current_step=steps[start_at].name if total else None,
        progress=int(start_at / total * 100) if total else 0,
    )

    try:
        await runner.prepare(ctx)
        for i, step in enumerate(steps):
            if i < start_at:
                continue
            await _patch(
                job_id,
                current_step=step.name,
                progress=int(i / total * 100),
                heartbeat_at=_now(),
            )
            started = _now()
            try:
                message = await runner.run_step(step, ctx)
            except Exception as exc:
                detail = f"{type(exc).__name__}: {exc}"
                log.warning("job_step_failed", job_id=str(job_id), step=step.name, error=detail)
                await _append_log(
                    job_id,
                    {
                        "step": step.name,
                        "title": step.title,
                        "status": "error",
                        "at": started.isoformat(),
                        "latency_ms": int((_now() - started).total_seconds() * 1000),
                        "message": detail,
                    },
                )
                # 失败步骤名留在 current_step 上 —— 重跑接口就是从它开始的
                await _patch(
                    job_id,
                    status="failed",
                    current_step=step.name,
                    finished_at=_now(),
                    error={"code": "step_failed", "step": step.name, "message": detail},
                )
                return
            await _append_log(
                job_id,
                {
                    "step": step.name,
                    "title": step.title,
                    "status": "ok",
                    "at": started.isoformat(),
                    "latency_ms": int((_now() - started).total_seconds() * 1000),
                    "message": message,
                },
            )
        await _patch(
            job_id,
            status=runner_cls.terminal_status,
            current_step=None,
            progress=100,
            finished_at=_now(),
            stats=ctx.scratch.get("stats", {}),
        )
        log.info("job_finished", job_id=str(job_id), status=runner_cls.terminal_status)
    except asyncio.CancelledError:
        # 进程被 kill / --reload 重启:任务就地消失。这里不落库(当前任务正在被取消,
        # 再 await 会立刻又被取消),交给启动时的 reap_abandoned_jobs() 收尸。
        log.info("job_cancelled", job_id=str(job_id))
        raise
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        log.exception("job_failed", job_id=str(job_id), error=detail)
        await _patch(
            job_id,
            status="failed",
            finished_at=_now(),
            error={"code": "job_failed", "message": detail},
        )
    finally:
        heartbeat.cancel()


async def retry_job(job_id: uuid.UUID) -> tuple[IngestJob, str]:
    """从失败的那一步重跑。返回 (job, 重跑起点步骤名);调用方负责派发 `execute_job`。"""
    async with SessionLocal() as session:
        job = await session.get(IngestJob, job_id)
        if job is None:
            raise NotFoundError(f"Job {job_id} not found")
        if job.status != "failed":
            raise ConflictError(
                f"Job is '{job.status}', only failed jobs can be retried",
                code="job_not_retryable",
            )
        names = [s.get("name") for s in job.steps]
        # current_step 是失败的那一步;万一它丢了(比如僵尸清理写的),就从头再跑
        from_step = job.current_step if job.current_step in names else (names[0] if names else None)
        if from_step is None:
            raise ConflictError("Job has no steps to retry", code="job_not_retryable")
        # 保留历史日志,只标一行分隔:审计上"重跑过"这件事本身有价值
        job.step_logs = [
            *job.step_logs,
            {
                "step": from_step,
                "title": "Retry",
                "status": "info",
                "at": _now().isoformat(),
                "message": f"Retrying from step '{from_step}'",
            },
        ]
        job.status = "queued"
        job.error = None
        await session.commit()
        await session.refresh(job)
    return job, from_step


async def reap_abandoned_jobs() -> int:
    """启动时收尸:把 `running` / `publishing` 的任务判为失败。

    **为什么可以这么武断**:执行器是进程内的 BackgroundTasks(刻意不上 Celery),
    进程一重启,内存里的任务就没了 —— 所以启动这一刻还标着 running 的,一定是僵尸。
    没有这一步,kill 一次后端就会留下一个永远 99% 的任务,演示时非常难看。
    """
    async with SessionLocal() as session:
        rows = (
            (
                await session.execute(
                    select(IngestJob).where(IngestJob.status.in_(("running", "publishing")))
                )
            )
            .scalars()
            .all()
        )
        for job in rows:
            job.status = "failed"
            job.finished_at = _now()
            job.error = {
                "code": "job_abandoned",
                "step": job.current_step,
                "message": "Worker restarted mid-run. Retry from the failed step.",
            }
            job.step_logs = [
                *job.step_logs,
                {
                    "step": job.current_step,
                    "title": "Abandoned",
                    "status": "error",
                    "at": _now().isoformat(),
                    "message": "Worker process restarted; job did not survive.",
                },
            ]
        await session.commit()
    if rows:
        log.warning("jobs_reaped", count=len(rows), ids=[str(j.id) for j in rows])
    return len(rows)


async def fail_if_stalled(job: IngestJob, session: Any) -> IngestJob:
    """惰性僵尸判定:进程还活着,但这个 running 任务的心跳早就停了。

    覆盖 `reap_abandoned_jobs()` 抓不到的情况(任务被取消/协程死了而进程没死)。
    放在查询接口里做,不额外起定时器 —— 没人看的任务不需要被判定。
    """
    if job.status != "running":
        return job
    last = job.heartbeat_at or job.started_at
    if last is None:
        return job
    if (_now() - last).total_seconds() <= JOB_HEARTBEAT_TIMEOUT_SEC:
        return job
    job.status = "failed"
    job.finished_at = _now()
    job.error = {
        "code": "job_stalled",
        "step": job.current_step,
        "message": f"No heartbeat for more than {JOB_HEARTBEAT_TIMEOUT_SEC}s.",
    }
    await session.commit()
    log.warning("job_stalled", job_id=str(job.id), step=job.current_step)
    return job
