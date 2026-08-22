"""问答与执行轨迹 schema。

`stream=true` 时接口返回的是 SSE 流,不走这些 response model;
它们描述的是非流式返回体与 trace 查询结果(前端类型由 openapi 生成,所以必须写全)。
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

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


class CitationExtra(BaseModel):
    """引用的附加信息。**故意允许多余字段**(`extra="allow"`):
    S1 只用得到分数/命中面/页码,S2 的文档引用会带 chunk 序号、S3 的问数会带 SQL 与行数;
    在这里把已知字段写出来是为了让前端有类型可用,不是为了封死结构。
    """

    model_config = ConfigDict(extra="allow")

    score: float | None = None
    matched_question: str | None = None
    is_standard_question: bool | None = None
    document_id: uuid.UUID | None = None
    page_idx: int | None = None
    bbox: list[float] | None = None


class MessageCitationOut(ORMModel):
    """一条引用(message_citations 表的一行)。

    以前它在 openapi 里是裸 `dict`,前端只能手写一份约定型 —— 违反"前端不许手写 API 类型"。
    出处:`app/core/chat.py::_exact_qa_citations`。
    """

    seq: int
    citation_type: str
    ref_id: uuid.UUID | None = None
    snippet: str | None = None
    extra: CitationExtra = CitationExtra()


class ChatResponse(BaseModel):
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    content: str
    status: str
    usage: dict
    cost_usd: Decimal
    latency_ms: int
    citations: list[MessageCitationOut] = []
    # true = 命中精准问答,内容是人工采纳过的标准答案原样返回(零改写、没过生成模型)
    verified: bool = False
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
