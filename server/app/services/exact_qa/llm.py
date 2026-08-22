"""结构化输出的小适配层 —— 把 Provider 的 `json_schema` 模式包成"给我一个 Pydantic 对象"。

沙箱里用的是 openai SDK 的 `client.responses.parse(text_format=Model)`,一行拿到对象;
Provider 层(S0 定型)提供的是更底层的 `complete(json_schema=...)` + `LLMResult.data`。
差的这一层就在这里补上,**三个调用点(抽取 / 相似问 / 命中复核)共用**,
不许各自手搓 schema —— 否则"忘了传 required"这种错会分别踩三遍。

用 Provider 而不是绕过它的三个理由(S0 的约定,不是形式主义):
1. 型号只由 `.env` 的 tier 映射决定,业务代码不写型号名;
2. 重试/超时/异常翻译/JSON 自愈统一在 Provider 里,这里不重复实现;
3. 每次调用都产出 usage 与 cost,trace 面板才有数(沙箱阶段是没有这层账的)。
"""

from pydantic import BaseModel, ValidationError

from app.core.errors import ProviderError
from app.providers import LLMResult, ModelTier, get_llm


async def parse_structured[T: BaseModel](
    model_cls: type[T],
    *,
    instructions: str,
    user_input: str,
    tier: ModelTier = "main",
    max_tokens: int = 4096,
) -> tuple[T, LLMResult]:
    """让模型按 `model_cls` 的形状回话,返回 (解析好的对象, 原始 LLMResult)。

    `LLMResult` 一起返回是为了 `span.record_llm(result)` —— 抽取一次几十秒、
    好几万 token,不记账的话 trace 面板上这条链路是个黑洞。
    """
    result = await get_llm().complete(
        [
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_input},
        ],
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
        # Provider 只校验"顶层 required 齐全",字段级校验在这里 —— 报错要带上原文才好查
        raise ProviderError(
            f"{model_cls.__name__}:模型输出不合 schema:{exc.error_count()} 处",
            detail={"errors": exc.errors()[:5], "raw": result.text[:500]},
            code="structured_output_invalid",
        ) from exc
