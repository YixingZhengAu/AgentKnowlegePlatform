"""OpenAI Embedding 实现。

两个刻意的保护:
- **维度断言**:实际返回的维度必须等于 `settings.embedding_dim`。向量列是
  `vector(EMBEDDING_DIM)`,维度不一致会在写库时才炸,而且可能悄悄写进错误的库;
  在这里挡住,报错直接指向"改了 EMBEDDING_MODEL 却没改 EMBEDDING_DIM"。
- **自动切批**:供应商单请求条数有上限,`embed()` 内部按 `EMBEDDING_BATCH_SIZE` 切,
  调用方(S1 一问一向量、S2 切块批量)不需要关心批量。
"""

import time
from collections.abc import Sequence

from openai import AsyncOpenAI

from app.config import Settings
from app.config import settings as default_settings
from app.core.errors import ConfigError
from app.core.logging import get_logger
from app.providers.base import EmbeddingResult, TokenUsage
from app.providers.pricing import estimate_cost
from app.providers.retry import with_retry

log = get_logger(__name__)


class OpenAIEmbeddingProvider:
    """EmbeddingProvider 的 OpenAI 实现。"""

    def __init__(self, settings: Settings | None = None):
        self._s = settings or default_settings
        self.dim = self._s.embedding_dim
        self._model = self._s.embedding_model
        self._batch = max(1, self._s.embedding_batch_size)
        self._client = AsyncOpenAI(
            api_key=self._s.openai_api_key,
            base_url=self._s.openai_base_url,
            timeout=self._s.embedding_timeout_sec,
            max_retries=0,
        )

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return (await self.embed_detailed(texts)).vectors

    async def embed_detailed(self, texts: Sequence[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(vectors=[], model=self._model, dim=self.dim)

        vectors: list[list[float]] = []
        usage = TokenUsage()
        t0 = time.perf_counter()

        for start in range(0, len(texts), self._batch):
            batch = list(texts[start : start + self._batch])
            raw = await with_retry(
                # dimensions:text-embedding-3-* 支持按需降维,保证与向量列一致
                lambda b=batch: self._client.embeddings.create(
                    model=self._model, input=b, dimensions=self.dim
                ),
                op=f"embedding.embed[{self._model}]",
                attempts=self._s.provider_max_attempts,
            )
            # 供应商不保证返回顺序,按 index 排回来
            for item in sorted(raw.data, key=lambda d: d.index):
                vec = list(item.embedding)
                if len(vec) != self.dim:
                    raise ConfigError(
                        f"Embedding 维度不匹配:模型 {self._model} 返回 {len(vec)} 维,"
                        f"但 EMBEDDING_DIM={self.dim}。改了 EMBEDDING_MODEL 就要同步改 "
                        f"EMBEDDING_DIM,并重建向量列(make db-reset)。",
                        code="embedding_dim_mismatch",
                    )
                vectors.append(vec)
            if raw.usage is not None:
                usage = usage + TokenUsage(prompt_tokens=raw.usage.prompt_tokens or 0)

        log.info(
            "embedding_done",
            model=self._model,
            count=len(vectors),
            dim=self.dim,
            batches=(len(texts) + self._batch - 1) // self._batch,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            prompt_tokens=usage.prompt_tokens,
        )
        return EmbeddingResult(
            vectors=vectors,
            model=self._model,
            dim=self.dim,
            usage=usage,
            cost_usd=estimate_cost(self._model, usage),
        )
