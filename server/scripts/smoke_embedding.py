"""Embedding 冒烟:embed 三句话,打印维度、token、成本与两两余弦相似度。

看点不只是"跑通":两句同义句的相似度应显著高于无关句,这说明向量是有意义的。
维度必须等于 EMBEDDING_DIM —— 不等就是 .env 配错了,向量列存不进去。

用法:uv run python -m scripts.smoke_embedding
"""

import asyncio
import math
import sys
import time

from app.config import settings
from app.core.errors import AppError
from app.providers import get_embedder

TEXTS = [
    "What is the warranty period for the mounting rails?",
    "How long is the warranty on the rails?",  # 与第一句同义
    "Our Melbourne warehouse shipped 1,240 units in July.",  # 无关
]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb)


async def main() -> int:
    emb = get_embedder()
    print(f"[smoke_embedding] model={settings.embedding_model} expect_dim={settings.embedding_dim}")

    t0 = time.perf_counter()
    res = await emb.embed_detailed(TEXTS)
    ms = int((time.perf_counter() - t0) * 1000)

    print(
        f"  count={len(res.vectors)} dim={res.dim} {ms}ms "
        f"prompt_tokens={res.usage.prompt_tokens} ${res.cost_usd}"
    )
    assert len(res.vectors) == len(TEXTS), "返回条数与输入不一致"
    for v in res.vectors:
        assert len(v) == settings.embedding_dim, f"维度 {len(v)} != EMBEDDING_DIM"

    print("  余弦相似度:")
    sim_same = cosine(res.vectors[0], res.vectors[1])
    sim_diff = cosine(res.vectors[0], res.vectors[2])
    print(f"    [0]x[1] 同义   = {sim_same:.4f}")
    print(f"    [0]x[2] 无关   = {sim_diff:.4f}")
    print(f"    [1]x[2] 无关   = {cosine(res.vectors[1], res.vectors[2]):.4f}")
    assert sim_same > sim_diff, "同义句相似度没有高于无关句,向量或模型有问题"

    print("[smoke_embedding] 全部通过 ✅")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except AppError as exc:
        print(f"[smoke_embedding] 失败({exc.code}): {exc.message}")
        if exc.detail:
            print(f"  detail={exc.detail}")
        sys.exit(1)
