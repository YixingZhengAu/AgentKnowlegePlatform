# server/app/providers/architect.md

## 设计要点(Step 4 实现前的约定)

- 三个 Protocol 全 async:`LLMProvider.complete/stream`、`EmbeddingProvider.embed`、`RerankProvider.rerank`
- **`model_tier`("main"/"light")而不是型号名**:业务代码只表达"要强模型还是快模型",
  映射在 `settings.model_for_tier()`。这是"分层用模型控成本"的落地
- `LLMResult` 统一带 `usage(prompt_tokens/completion_tokens)` 与 `cost_estimate`,给 Trace 框架直接消费
- `json_schema` 参数:结构化输出统一走这里(S1 抽 QA、S4 路由决策都靠它),校验失败自动重试 2 次
- 统一重试(指数退避)与超时;供应商特定报错翻译成 `ProviderError`(app/core/errors.py)
- Rerank:S0/S2 先用 `PassthroughReranker`(原序返回),S2 按实测效果决定是否引入真实 Rerank(U5)
- Embedding 维度以 `settings.embedding_dim` 为准,实现里做一次断言,防止换模型后维度不匹配悄悄写库
