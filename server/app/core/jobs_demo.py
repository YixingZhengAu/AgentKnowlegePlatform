"""`DemoSleepJob` —— 用来验证 Job 框架本身的假任务(S0-PLAN Step 7.3)。

别小看它:S1 的真抽取任务写出来之前,前端的进度条组件需要一个**稳定、可控、不花钱**
的联调对象 —— 能按需慢、能按需失败、能按需产出待审条目。

三个可调参数(`POST /api/jobs` 的 params):

| 参数 | 默认 | 作用 |
| --- | --- | --- |
| `step_seconds` | 2 | 每步睡多久(演示进度条) |
| `items` | 20 | 最后一步写多少条 staging_items(Step 8 审核台的素材) |
| `fail_at` | 无 | 指定步骤名,让它失败一次 —— 用来演示"从失败步骤重跑" |

`fail_at` 是**只失败一次**:重跑时框架会发现这步已经有一条 error 日志,于是放它过去。
不这么做的话"重试"按钮永远重试失败,演示不出恢复路径。
"""

import asyncio
import uuid

from sqlalchemy import select

from app.core.jobs import JobRunContext, JobRunner, JobStepDef, register_job
from app.db import SessionLocal
from app.models import IngestJob, StagingItem

# 假 QA 素材(全英文,D5)。写成模板 + 序号,20 条也不重复。
_TOPICS = [
    ("warranty period", "The standard warranty covers 5 years on the unit"),
    ("shipping lead time", "Standard lead time is 6 weeks from order confirmation"),
    ("mounting compatibility", "The rail system fits tile, metal and flat roofs"),
    ("inverter pairing", "Any inverter with a 600 V DC input window is supported"),
    ("cycle life", "Rated for 6000 cycles at 80% depth of discharge"),
]


@register_job
class DemoSleepJob(JobRunner):
    """四步、每步睡两秒、最后写一批待审条目。"""

    job_type = "demo_sleep"
    steps = [
        JobStepDef("fetch", "Fetch source"),
        JobStepDef("parse", "Parse content"),
        JobStepDef("extract", "Extract candidates"),
        JobStepDef("stage", "Write staging items"),
    ]
    # 摄取类任务跑完停在 review 等人审(Step 8 的审核台从这里接手)
    terminal_status = "review"

    async def prepare(self, ctx: JobRunContext) -> None:
        ctx.scratch["seconds"] = float(ctx.params.get("step_seconds", 2))
        ctx.scratch["items"] = int(ctx.params.get("items", 20))

    # ---------------------------------------------------------------- 步骤

    async def step_fetch(self, ctx: JobRunContext) -> str:
        await self._tick(ctx, "fetch")
        return "Loaded 1 source document (demo, nothing was actually read)"

    async def step_parse(self, ctx: JobRunContext) -> str:
        await self._tick(ctx, "parse")
        return "Parsed 8 sections / 1,240 words"

    async def step_extract(self, ctx: JobRunContext) -> str:
        await self._tick(ctx, "extract")
        n = ctx.scratch["items"]
        return f"Extracted {n} candidate QA pairs"

    async def step_stage(self, ctx: JobRunContext) -> str:
        await self._tick(ctx, "stage")
        n = ctx.scratch["items"]
        async with SessionLocal() as session:
            # 幂等:重跑这一步不该把条目写两遍
            existing = (
                await session.execute(
                    select(StagingItem.id).where(StagingItem.job_id == ctx.job_id)
                )
            ).all()
            if existing:
                return f"{len(existing)} staging items already written, nothing to do"
            session.add_all([self._fake_item(ctx, i) for i in range(n)])
            await session.commit()
        ctx.scratch["stats"] = {"staged": n}
        return f"Wrote {n} staging items, waiting for review"

    # ---------------------------------------------------------------- 内部

    async def _tick(self, ctx: JobRunContext, step: str) -> None:
        """睡一会儿,然后按 fail_at 决定是不是该在这里炸一次。"""
        await asyncio.sleep(ctx.scratch["seconds"])
        if ctx.params.get("fail_at") != step:
            return
        if await self._already_failed(ctx.job_id, step):
            return  # 已经失败过一次了,这次是重跑,放它过去
        raise RuntimeError(f"Injected failure at step '{step}' (fail_at param)")

    @staticmethod
    async def _already_failed(job_id: uuid.UUID, step: str) -> bool:
        async with SessionLocal() as session:
            job = await session.get(IngestJob, job_id)
            if job is None:
                return False
            return any(
                log.get("step") == step and log.get("status") == "error" for log in job.step_logs
            )

    @staticmethod
    def _fake_item(ctx: JobRunContext, i: int) -> StagingItem:
        topic, answer = _TOPICS[i % len(_TOPICS)]
        # 置信度铺开成三档,好让审核台的排序/筛选有东西可筛
        confidence = round(0.62 + (i % 7) * 0.055, 3)
        return StagingItem(
            job_id=ctx.job_id,
            kb_id=ctx.kb_id,
            item_type="qa_pair",
            payload={
                "standard_question": f"What is the {topic} for model HC-{215 + i}?",
                "answer": f"{answer} (HC-{215 + i}).",
                "similar_questions": [f"HC-{215 + i} {topic}", f"{topic} HC{215 + i}"],
                "keywords": [topic.split()[0], f"HC-{215 + i}"],
            },
            origin_ref={"page": 1 + i // 4, "quote": f"…{topic}…"},
            confidence=confidence,
        )
