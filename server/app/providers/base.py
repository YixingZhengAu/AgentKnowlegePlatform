"""Provider 抽象:LLM / Embedding / Rerank 三个 Protocol 与它们的返回类型。

两条不可动摇的约定:
1. 业务代码只说 `model_tier="main" | "light"`(要强模型还是快模型),**不写型号名**;
   tier→型号的映射只存在于 `.env` + `settings.model_for_tier()`。
2. 每次调用都要能产出 `TokenUsage` 与 `cost_usd`,Trace 框架直接消费(app/core/trace.py)。
"""

import base64
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol, TypedDict, runtime_checkable

ModelTier = Literal["main", "light"]
Role = Literal["system", "user", "assistant"]


class TextPart(TypedDict):
    """多模态消息里的一段文字。"""

    type: Literal["text"]
    text: str


class _ImageUrl(TypedDict):
    url: str


class ImagePart(TypedDict):
    """多模态消息里的一张图。`url` 用 data URI(见 `image_part()`)。"""

    type: Literal["image_url"]
    image_url: _ImageUrl


class ChatMessage(TypedDict):
    """给 LLM 的一条消息。刻意用 TypedDict 而不是 Pydantic:这层是热路径,不需要校验开销。

    `content` 支持两种形态(契约变更 C6,S2 引入):
    - `str` —— 纯文本,**既有调用零改动**;
    - `list[TextPart | ImagePart]` —— 图文混排,S2 描述图表时要把截图交给模型。

    这两种形态的字典结构与 OpenAI Chat Completions 的线上格式逐字一致,
    所以 `openai_llm.py` 原样透传即可,不需要任何转换分支。
    """

    role: Role
    content: str | list[TextPart | ImagePart]


def image_part(data: bytes, mime: str = "image/jpeg") -> ImagePart:
    """把图片字节包成一条 `ImagePart`(data URI,不依赖任何可公网访问的图床)。

    Args:
        data: 图片原始字节。
        mime: MIME 类型,MinerU 落盘的截图是 jpeg。

    Returns:
        可直接放进 `ChatMessage["content"]` 列表里的一段。
    """
    b64 = base64.b64encode(data).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """一个 stage 里调了多次模型(比如 JSON 模式重试)时把用量累加。"""
        return TokenUsage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(slots=True)
class LLMResult:
    text: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: Decimal = Decimal("0")
    finish_reason: str | None = None
    # json_schema 模式下解析好的对象(非 JSON 模式为 None)
    data: dict | None = None
    # 同一次逻辑调用实际发出的请求数(JSON 校验失败重试会 >1),冒烟脚本和 trace 都看它
    attempts: int = 1


@dataclass(slots=True)
class StreamEvent:
    """流式事件。token 事件只带增量文本;end 事件带完整的 LLMResult(含 usage)。"""

    type: Literal["token", "end"]
    text: str = ""
    result: LLMResult | None = None


@dataclass(slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dim: int
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost_usd: Decimal = Decimal("0")


@dataclass(slots=True)
class RerankHit:
    index: int  # 在入参 docs 里的下标
    score: float
    document: str


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_tier: ModelTier = "main",
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResult: ...

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_tier: ModelTier = "main",
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AsyncIterator[StreamEvent]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    dim: int

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_detailed(self, texts: Sequence[str]) -> EmbeddingResult: ...


@runtime_checkable
class RerankProvider(Protocol):
    async def rerank(self, query: str, docs: Sequence[str], top_n: int) -> list[RerankHit]: ...
