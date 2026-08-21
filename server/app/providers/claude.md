# server/app/providers/

**职责**:外部模型供应商的抽象与实现(LLM / Embedding / Rerank)。业务代码只 `from app.providers import get_llm, get_embedder, get_reranker`。

| 文件 | 内容 |
| --- | --- |
| `base.py` | 三个 Protocol + `LLMResult` / `StreamEvent` / `TokenUsage` / `EmbeddingResult` / `RerankHit` / `ChatMessage` |
| `registry.py` | `get_llm()` / `get_embedder()` / `get_reranker()`:按 `.env` 选实现,单例 |
| `openai_llm.py` | `OpenAILLMProvider`:complete / stream / JSON 模式 / 参数能力回退 |
| `openai_embedding.py` | `OpenAIEmbeddingProvider`:自动切批 + 维度断言 |
| `passthrough_rerank.py` | `PassthroughReranker`:原序返回(U5) |
| `pricing.py` | 价格表 + `estimate_cost()`(token → 美元) |
| `retry.py` | `with_retry()` 指数退避 + `translate_error()` 异常翻译 |
| `__init__.py` | 对外出口(只从这里 import) |

冒烟脚本:`server/scripts/smoke_llm.py`、`smoke_embedding.py`;离线测试:`server/tests/test_providers.py`。

详见 `architect.md`。
