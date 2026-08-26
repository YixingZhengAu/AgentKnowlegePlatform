# server/app/providers/

**职责**:外部模型供应商的抽象与实现(LLM / Embedding / Rerank)。业务代码只 `from app.providers import get_llm, get_embedder, get_reranker`。

| 文件 | 内容 |
| --- | --- |
| `base.py` | 三个 Protocol + `LLMResult` / `StreamEvent` / `TokenUsage` / `EmbeddingResult` / `RerankHit` / `ChatMessage`(**C6:`content` 支持 `str \| list[TextPart \| ImagePart]`**,附 `image_part()`) |
| `registry.py` | `get_llm()` / `get_embedder()` / `get_reranker()`:按 `.env` 选实现,单例 |
| `openai_llm.py` | `OpenAILLMProvider`:complete / stream / JSON 模式 / 参数能力回退 |
| `openai_embedding.py` | `OpenAIEmbeddingProvider`:自动切批 + 维度断言 |
| `passthrough_rerank.py` | `PassthroughReranker`:原序返回(U5 占位实现) |
| `cross_encoder_rerank.py` | `CrossEncoderReranker`(**C7,S2 引入**):本地 cross-encoder 真重排;CPU 推理走 `asyncio.to_thread`;`guard` 策略在整题失灵时退回召回名次 |
| `mineru.py` | **C3,S2 上提**:MinerU 解析服务的 HTTP 客户端(`call_mineru` / `as_json`)—— S1 与 S2 都要解析 PDF,而域与域互不 import,所以住在供应商层 |
| `pricing.py` | 价格表 + `estimate_cost()`(token → 美元) |
| `retry.py` | `with_retry()` 指数退避 + `translate_error()` 异常翻译 |
| `__init__.py` | 对外出口(只从这里 import) |

冒烟脚本:`server/scripts/smoke_llm.py`、`smoke_embedding.py`;离线测试:`server/tests/test_providers.py`。

详见 `architect.md`。
