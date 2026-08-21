"""Job 框架的离线测试(不碰 DB):注册表、步骤分发、假任务产物形状。

执行器 `execute_job()` 本身要写库,不在这里测 —— 它的验证在 Step 7 的接口实测里
(提交 → 进度 → 失败 → 从失败步骤重跑 → kill 进程后收尸)。
"""

from uuid import uuid4

import pytest

from app.core.errors import NotFoundError
from app.core.jobs import (
    JobRunContext,
    JobRunner,
    JobStepDef,
    get_runner_cls,
    known_job_types,
    register_job,
)
from app.core.jobs_demo import DemoSleepJob


def _ctx(**params) -> JobRunContext:
    return JobRunContext(job_id=uuid4(), kb_id=uuid4(), source_id=None, params=params)


def test_demo_job_is_registered():
    assert "demo_sleep" in known_job_types()
    assert get_runner_cls("demo_sleep") is DemoSleepJob


def test_unknown_job_type_is_not_found():
    with pytest.raises(NotFoundError) as exc:
        get_runner_cls("no_such_job")
    assert exc.value.code == "unknown_job_type"


def test_steps_are_declarative():
    """步骤是数据而不是代码流程:前端在任务开始前就能画出全部步骤。"""
    names = [s.name for s in DemoSleepJob.steps]
    assert names == ["fetch", "parse", "extract", "stage"]
    assert all(s.title for s in DemoSleepJob.steps)


async def test_run_step_dispatches_by_convention():
    calls: list[str] = []

    @register_job
    class _Probe(JobRunner):
        job_type = "_probe"
        steps = [JobStepDef("alpha", "Alpha")]

        async def prepare(self, ctx: JobRunContext) -> None:
            calls.append("prepare")

        async def step_alpha(self, ctx: JobRunContext) -> str:
            calls.append("alpha")
            return "did alpha"

    runner = _Probe()
    ctx = _ctx()
    await runner.prepare(ctx)
    assert await runner.run_step(_Probe.steps[0], ctx) == "did alpha"
    assert calls == ["prepare", "alpha"]


async def test_missing_step_handler_raises():
    @register_job
    class _Broken(JobRunner):
        job_type = "_broken"
        steps = [JobStepDef("ghost", "Ghost")]

        async def prepare(self, ctx: JobRunContext) -> None: ...

    with pytest.raises(NotImplementedError, match="step_ghost"):
        await _Broken().run_step(_Broken.steps[0], _ctx())


async def test_prepare_reads_params_with_defaults():
    ctx = _ctx()
    await DemoSleepJob().prepare(ctx)
    assert ctx.scratch == {"seconds": 2.0, "items": 20}

    ctx = _ctx(step_seconds=0.25, items=3)
    await DemoSleepJob().prepare(ctx)
    assert ctx.scratch == {"seconds": 0.25, "items": 3}


def test_fake_item_payload_matches_qa_pair_schema():
    """payload 形状必须与 DB-DESIGN §8 的 qa_pair 一致 —— Step 8 的审核台按它渲染。"""
    ctx = _ctx()
    item = DemoSleepJob._fake_item(ctx, 0)
    assert item.item_type == "qa_pair"
    assert set(item.payload) == {"standard_question", "answer", "similar_questions", "keywords"}
    assert 0 <= item.confidence <= 1
    assert item.origin_ref["page"] >= 1


def test_fake_items_spread_confidence():
    """置信度要铺开:审核台的排序与筛选需要有区分度的数据。"""
    ctx = _ctx()
    values = {DemoSleepJob._fake_item(ctx, i).confidence for i in range(20)}
    assert len(values) >= 5
    assert min(values) < 0.75 < max(values)
