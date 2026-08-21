"""问答与执行轨迹 schema。

`stream=true` 时接口返回的是 SSE 流,不走这些 response model;
它们描述的是非流式返回体与 trace 查询结果(前端类型由 openapi 生成,所以必须写全)。
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    # 不传就新开一轮会话(前端"新对话"不需要先建会话)
    conversation_id: uuid.UUID | None = None
    stream: bool = True


class TraceSpanOut(BaseModel):
    """流式/非流式返回体里附带的轻量 trace(前端执行轨迹面板直接用)。"""

    stage: str
    seq: int
    status: str
    latency_ms: int | None = None
    model: str | None = None
    usage: dict | None = None
    cost_usd: str | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    content: str
    status: str
    usage: dict
    cost_usd: Decimal
    latency_ms: int
    citations: list[dict] = []
    trace: list[TraceSpanOut] = []


class TraceOut(ORMModel):
    """traces 表的一行(GET /api/traces/{message_id})。"""

    id: uuid.UUID
    message_id: uuid.UUID
    stage: str
    seq: int
    status: str
    input: dict | None
    output: dict | None
    error: str | None
    latency_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: Decimal | None
    model: str | None
    created_at: datetime
