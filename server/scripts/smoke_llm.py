"""LLM 冒烟:一次补全 + 一次流式 + 一次 JSON 模式,打印型号/耗时/token/成本。

这是六步法第 ② 步在 S0 的体现:接 HTTP 之前先在命令行确认 key 有效、网络通、
流式能吐字、结构化输出能用。任何一项红,后面的链路都不用查了。

用法:uv run python -m scripts.smoke_llm
"""

import asyncio
import json
import sys
import time

from app.config import settings
from app.core.errors import AppError
from app.providers import ChatMessage, get_llm

SYSTEM: ChatMessage = {
    "role": "system",
    "content": "You are a concise assistant for an Australian solar mounting company.",
}

ROUTE_SCHEMA = {
    "name": "route_decision",
    "schema": {
        "type": "object",
        "properties": {
            "targets": {
                "type": "array",
                "items": {"type": "string", "enum": ["exact_qa", "document", "text2sql"]},
            },
            "reason": {"type": "string"},
        },
        "required": ["targets", "reason"],
        "additionalProperties": False,
    },
}


def _fmt(label: str, model: str, ms: int, usage, cost) -> str:
    return (
        f"  {label:<12} model={model}  {ms}ms  "
        f"prompt={usage.prompt_tokens} completion={usage.completion_tokens}  ${cost}"
    )


async def main() -> int:
    llm = get_llm()
    print(f"[smoke_llm] main={settings.llm_model_main} light={settings.llm_model_light}")

    # ① 普通补全(light tier:冒烟用便宜模型)
    t0 = time.perf_counter()
    r1 = await llm.complete(
        [SYSTEM, {"role": "user", "content": "Reply with exactly: SMOKE OK"}],
        model_tier="light",
        max_tokens=64,
    )
    print("① complete")
    print(_fmt("light", r1.model, int((time.perf_counter() - t0) * 1000), r1.usage, r1.cost_usd))
    print(f"  text={r1.text.strip()!r}")
    assert r1.text.strip(), "补全返回空文本"

    # ② 流式:关注"第一个 token 多久到"(TTFB),这决定对话页的体感
    print("② stream")
    t0 = time.perf_counter()
    first_ms: int | None = None
    tokens = 0
    final = None
    async for ev in llm.stream(
        [SYSTEM, {"role": "user", "content": "In one sentence, what is a solar mounting rail?"}],
        model_tier="light",
        max_tokens=120,
    ):
        if ev.type == "token":
            tokens += 1
            if first_ms is None:
                first_ms = int((time.perf_counter() - t0) * 1000)
            print(ev.text, end="", flush=True)
        else:
            final = ev.result
    print()
    assert final is not None and final.text.strip(), "流式没有拿到 end 事件或文本为空"
    print(
        _fmt(
            "light",
            final.model,
            int((time.perf_counter() - t0) * 1000),
            final.usage,
            final.cost_usd,
        )
    )
    print(f"  chunks={tokens}  first_token={first_ms}ms")

    # ③ JSON 模式(S4 路由决策就长这样)
    print("③ json_schema")
    t0 = time.perf_counter()
    r3 = await llm.complete(
        [
            SYSTEM,
            {
                "role": "user",
                "content": (
                    "Which knowledge sources answer this question: "
                    "'How many rail units did we ship in July?' "
                    "Options: exact_qa (curated QA), document (manuals), text2sql (business DB)."
                ),
            },
        ],
        model_tier="light",
        max_tokens=256,
        json_schema=ROUTE_SCHEMA,
    )
    print(_fmt("light", r3.model, int((time.perf_counter() - t0) * 1000), r3.usage, r3.cost_usd))
    print(f"  attempts={r3.attempts}  data={json.dumps(r3.data, ensure_ascii=False)}")
    assert r3.data and r3.data.get("targets"), "JSON 模式没有拿到 targets"

    print("[smoke_llm] 全部通过 ✅")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except AppError as exc:  # 配置/供应商类错误:只打关键信息,不刷栈
        print(f"[smoke_llm] 失败({exc.code}): {exc.message}")
        if exc.detail:
            print(f"  detail={exc.detail}")
        sys.exit(1)
