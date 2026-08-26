"""Rerank 真实实现:本地 cross-encoder(契约变更 C7,S2 引入)。

与 bi-encoder(embedding)的区别:query 与候选**拼在一起**过一遍模型
(`[CLS] query [SEP] doc [SEP]`),靠交叉注意力直接输出一个相关性分数。
不能预计算,所以只用在召回之后的少量候选上 —— 这正是"重排"这一步存在的意义。

**加载 ~3s,不是 11s**:`sentence-transformers` 每次加载都会去 HuggingFace 核对版本
(实测这一趟网络往返 8.6s),所以默认 `HF_HUB_OFFLINE=1` 强制走本地缓存 ——
权重由 bootstrap 的"预下载重排模型"那一步提前备好。

**为什么进程内而不是单起容器**(S2 Step 5 实测,见 `documents/S2-PLAN.md` C1 的 C7 一节):
30 条候选一次重排中位 **207ms**,不值得为它多维护一个容器;
但加载那 3 秒不该落在第一个用户请求上 —— 所以构造时就在后台线程开始加载。

**`guard` 策略**(实测定稿):cross-encoder 偶尔会整题失灵 ——
对所有候选都打负分,这时它的排序就是噪声。判据不是单条分数(跨题不可比),
而是**整题的最高分**:低于 `DOC_RAG_RERANK_GUARD` 就原序返回,
把排序权交还给上游的召回融合。评测集实测 90% → 95%。
"""

import asyncio
import os
import threading
from collections.abc import Sequence

from app.config import Settings
from app.config import settings as default_settings
from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.providers.base import RerankHit

log = get_logger(__name__)


class CrossEncoderReranker:
    """RerankProvider 的 cross-encoder 实现。

    Attributes:
        settings: 配置对象,决定型号、截断长度与 guard 阈值。
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or default_settings
        self._model = None
        self._lock = threading.Lock()
        # 后台预热:那几秒加载不要落在第一个请求上
        threading.Thread(target=self._ensure_model, daemon=True).start()

    # ─── 私有 ─────────────────────────────────────────────────────────────────

    def _ensure_model(self):
        """加载并缓存模型(线程安全,重复调用只加载一次)。

        Returns:
            已加载的 `CrossEncoder`。

        Raises:
            ProviderError: 依赖缺失或权重下载失败。
        """
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            name = self.settings.doc_rag_rerank_model
            # 🩸 必须在 import 之前设:HuggingFace 的客户端在 import 期读这个变量。
            # 开着它,加载 13.2s → 3.1s(省掉每次启动都去 Hub 核对版本的那趟网络往返)。
            if self.settings.doc_rag_rerank_offline:
                os.environ.setdefault("HF_HUB_OFFLINE", "1")
            try:
                from sentence_transformers import CrossEncoder

                log.info("rerank_model_loading", model=name)
                self._model = CrossEncoder(name, max_length=512)
                log.info("rerank_model_ready", model=name)
            except Exception as exc:  # noqa: BLE001 报错要说清怎么修
                raise ProviderError(
                    f"重排模型 {name} 加载失败。权重需要先下到本地缓存:"
                    "跑 ./bootstrap.sh 或 make rerank-model。"
                    "(离线模式由 DOC_RAG_RERANK_OFFLINE 控制,默认开)",
                    detail={"model": name, "error": str(exc)},
                ) from exc
        return self._model

    def _truncate(self, text: str) -> str:
        """按**模型自己的分词器**截断,与实测口径一致。

        用模型的 tokenizer 而不是 tiktoken:512 是 BERT 家族的位置数硬上限,
        query 与候选共用这个预算,截断口径必须和模型一致才算得准。
        """
        tokenizer = self._ensure_model().tokenizer
        ids = tokenizer(
            text,
            add_special_tokens=False,
            truncation=True,
            max_length=self.settings.doc_rag_rerank_max_tokens,
        )["input_ids"]
        return tokenizer.decode(ids)

    def _score(self, query: str, docs: Sequence[str]) -> list[float]:
        """同步打分 —— 由 `rerank()` 丢进线程池,不阻塞事件循环。"""
        model = self._ensure_model()
        pairs = [(query, self._truncate(d)) for d in docs]
        return [float(s) for s in model.predict(pairs)]

    # ─── 公共 ─────────────────────────────────────────────────────────────────

    async def rerank(self, query: str, docs: Sequence[str], top_n: int) -> list[RerankHit]:
        """给候选重新排序,返回前 `top_n`。

        Args:
            query: 用户问题(或改写后的单条 query)。
            docs: 候选正文,**必须按上游召回融合的名次传入** ——
                `guard` 触发时原序返回,靠的就是这个顺序。
            top_n: 返回条数。

        Returns:
            `RerankHit` 列表;`index` 是在入参 `docs` 里的下标。
        """
        if not docs or top_n <= 0:
            return []

        # CPU 推理是阻塞的,必须挪出事件循环,否则整个服务被一次重排卡住
        scores = await asyncio.to_thread(self._score, query, docs)

        strategy = self.settings.doc_rag_rerank_strategy
        if strategy == "guard" and max(scores) < self.settings.doc_rag_rerank_guard:
            # 整题失灵:模型对所有候选都投了否决票,它的排序不可信 → 交还给召回名次
            log.info(
                "rerank_guard_fallback",
                top_score=round(max(scores), 3),
                threshold=self.settings.doc_rag_rerank_guard,
                candidates=len(docs),
            )
            order = range(len(docs))
        else:
            order = sorted(range(len(docs)), key=lambda i: -scores[i])

        return [
            RerankHit(index=i, score=scores[i], document=docs[i])
            for i in list(order)[:top_n]
        ]
