"""Rerank 占位实现:原序返回(U5 决策)。

S0/S2 先不引入真实 rerank —— 先把接口占住,让 S2 的检索链路能无改动地插入真实实现。
score 用"位置倒数"造一个单调递减的分,前端/日志里看到的形状与真实 reranker 一致。
"""

from collections.abc import Sequence

from app.providers.base import RerankHit


class PassthroughReranker:
    """RerankProvider 的透传实现:不重排,只截断到 top_n。"""

    async def rerank(self, query: str, docs: Sequence[str], top_n: int) -> list[RerankHit]:
        del query  # 透传实现不看 query,签名保持一致
        return [
            RerankHit(index=i, score=1.0 / (i + 1), document=d)
            for i, d in enumerate(docs[: max(0, top_n)])
        ]
