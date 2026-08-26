"""Provider 注册表:按配置选实现,全局单例(客户端里有连接池,不要每次新建)。

业务代码只 `from app.providers import get_llm` —— 换供应商是改 .env,不是改调用点。
"""

from functools import lru_cache

from app.config import settings
from app.core.errors import ConfigError
from app.providers.base import EmbeddingProvider, LLMProvider, RerankProvider
from app.providers.cross_encoder_rerank import CrossEncoderReranker
from app.providers.openai_embedding import OpenAIEmbeddingProvider
from app.providers.openai_llm import OpenAILLMProvider
from app.providers.passthrough_rerank import PassthroughReranker


@lru_cache
def get_llm() -> LLMProvider:
    if settings.llm_provider == "openai":
        return OpenAILLMProvider()
    raise ConfigError(f"未知的 LLM_PROVIDER={settings.llm_provider}", code="unknown_provider")


@lru_cache
def get_embedder() -> EmbeddingProvider:
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider()
    raise ConfigError(
        f"未知的 EMBEDDING_PROVIDER={settings.embedding_provider}", code="unknown_provider"
    )


@lru_cache
def get_reranker() -> RerankProvider:
    if settings.rerank_provider == "passthrough":
        return PassthroughReranker()
    if settings.rerank_provider == "cross_encoder":
        return CrossEncoderReranker()
    raise ConfigError(f"未知的 RERANK_PROVIDER={settings.rerank_provider}", code="unknown_provider")
