"""结构化输出适配:Provider 的 `json_schema` 模式 → Pydantic 对象。

与 S1 的同名文件只差一处:这里的 `user_content` 允许是**图文混排**
(`list[TextPart | ImagePart]`,契约变更 C6)—— 图表描述必须把截图交给模型,
只喂 OCR 出来的 HTML 是不够的(实测 MinerU 的表格 HTML 会漏行、错行)。

**不 import 兄弟域**:S1 的 `services/exact_qa/llm.py` 形状几乎一样,
但域与域互不 import 是硬纪律,所以这里各写一份。
"""

from collections.abc import Sequence

from pydantic import BaseModel, ValidationError

from app.core.errors import ProviderError
from app.providers import ChatMessage, ImagePart, LLMResult, ModelTier, TextPart, get_llm


async def parse_structured[T: BaseModel](
    model_cls: type[T],
    *,
    instructions: str,
    user_content: str | Sequence[TextPart | ImagePart],
    tier: ModelTier = "light",
    max_tokens: int = 4096,
) -> tuple[T, LLMResult]:
    """让模型按 `model_cls` 的 schema 输出,解析成对象。

    Args:
        model_cls: 期望的输出形状。
        instructions: system 提示词。
        user_content: 用户消息 —— 纯文本,或图文混排的分段列表。
        tier: 模型档位;图表描述用 light 就够(实测 gpt-5-mini 质量达标)。
        max_tokens: 回答预算(推理型模型的思考预算由 Provider 另加)。

    Returns:
        `(解析好的对象, 原始 LLMResult)`;后者带 usage 与 cost,给 trace 记账。

    Raises:
        ProviderError: 模型没返回 JSON,或返回的 JSON 不合 schema。
    """
    content = user_content if isinstance(user_content, str) else list(user_content)
    messages: list[ChatMessage] = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": content},
    ]
    result = await get_llm().complete(
        messages,
        model_tier=tier,
        max_tokens=max_tokens,
        json_schema={"name": model_cls.__name__, "schema": model_cls.model_json_schema()},
    )
    if result.data is None:
        raise ProviderError(
            f"{model_cls.__name__}:模型没有返回可解析的 JSON",
            detail={"raw": result.text[:500]},
            code="structured_output_missing",
        )
    try:
        return model_cls.model_validate(result.data), result
    except ValidationError as exc:
        raise ProviderError(
            f"{model_cls.__name__}:模型输出不合 schema:{exc.error_count()} 处",
            detail={"errors": exc.errors()[:5], "raw": result.text[:500]},
            code="structured_output_invalid",
        ) from exc
