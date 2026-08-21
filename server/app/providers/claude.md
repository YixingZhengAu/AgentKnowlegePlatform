# server/app/providers/

**职责**:外部模型供应商的抽象与实现(LLM / Embedding / Rerank)。

**当前为空 —— Step 4 填充。**

计划文件:`base.py`(三个 Protocol + `LLMResult` / `StreamEvent` / `RerankHit`)、
`openai_llm.py`、`openai_embedding.py`、`passthrough_rerank.py`、`registry.py`(按配置选实现)。

详见 `architect.md`。
