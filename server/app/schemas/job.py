"""摄取 Job 的出入参。

`steps` / `step_logs` / `error` / `stats` 都是 jsonb,这里刻意保持成宽松的 dict/list:
它们的内部结构由 Job 框架与各 Job 子类决定,前端进度条按约定字段渲染
(见 `app/core/architect.md` 的 Job 框架一节),不值得为每个子类各生成一套类型。
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class JobSubmitRequest(BaseModel):
    # 已注册的 job_type(S0 只有 demo_sleep);未知类型返回 404 unknown_job_type
    job_type: str = Field(min_length=1, max_length=64)
    kb_id: uuid.UUID
    source_id: uuid.UUID | None = None
    params: dict = {}


class JobOut(ORMModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    source_id: uuid.UUID | None
    job_type: str
    status: str
    # 声明式步骤骨架:[{"name":"parse","title":"Parse content"}]
    steps: list[dict]
    current_step: str | None
    progress: int
    # 分步日志:[{"step","title","status","at","latency_ms","message"}]
    step_logs: list[dict]
    error: dict | None
    params: dict
    stats: dict
    heartbeat_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
