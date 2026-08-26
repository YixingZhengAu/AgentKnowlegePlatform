# server/app/providers/architect.md

## 设计要点

- 三个 Protocol 全 async:`LLMProvider.complete/stream`、`EmbeddingProvider.embed/embed_detailed`、`RerankProvider.rerank`
- **`model_tier`("main"/"light")而不是型号名**:业务代码只表达"要强模型还是快模型",
  映射在 `settings.model_for_tier()`。这是"分层用模型控成本"的落地
- `LLMResult` 带 `usage(prompt/completion)` + `cost_usd` + `model`,Trace 框架(`app/core/trace.py`)直接消费
- `json_schema` 参数:结构化输出统一走这里(S1 抽 QA、S4 路由决策都靠它)
- 统一重试(指数退避)与超时;供应商报错翻译成 `ProviderError` / `ConfigError`
- Rerank:S0/S2 先透传(U5),S2 按实测效果决定是否引入真实 Rerank
- Embedding 维度以 `settings.embedding_dim` 为准,实现里逐条断言

## 调用链

```
业务代码 → registry.get_llm()(lru_cache 单例)
        → OpenAILLMProvider.complete()
        → _payload()  组装参数(tier→型号、推理模型加 headroom)
        → with_retry(_create)  瞬时故障退避重试
        → _create()  参数能力回退(被拒的参数记住并去掉)
        → _guard_empty() + estimate_cost() → LLMResult
```

## 四个必须知道的实现细节

### 1. 推理型模型的 token 预算(踩过的坑)

`gpt-5` 系是推理模型,**思考 token 与回答 token 共用 `max_completion_tokens`**。
第一次冒烟时传 `max_tokens=64`,64 个 token 全被思考吃掉,`content` 是空字符串、
`finish_reason=length` —— 表现为"调用成功但没有回答"。

处理:`_payload()` 里对 `_REASONING_PREFIXES`(gpt-5 / o1 / o3 / o4)开头的型号,
实际发出的 `max_completion_tokens = max_tokens + LLM_REASONING_HEADROOM`(默认 2048),
并带 `reasoning_effort=LLM_REASONING_EFFORT`(默认 low,演示延迟可接受)。
于是 `max_tokens` 的语义始终是"给回答的预算",调用方不用关心是不是推理模型。

`_guard_empty()` 兜底:仍拿到空回复就抛 `ProviderError`,报错里直接写"调大 max_tokens
或 LLM_REASONING_HEADROOM,或把 LLM_REASONING_EFFORT 降到 minimal"。**不允许把空串静默返回给上层。**

### 2. 参数能力回退(`_UNSUPPORTED`)

推理模型不接受 `temperature`。硬编码"哪个型号支持什么"会在换型号时过期,所以:
被 400 拒绝一次 → 从报错 body 的 `param` 认出是哪个参数 → 记进进程级 `_UNSUPPORTED`
→ 去掉重发,且该进程后续调用不再带它。`_DROPPABLE` 里只放"去掉只影响效果、不影响语义"的参数。

推理模型的 `temperature` 是已知不支持,`_payload()` 里直接不带(省掉那次被拒的往返)。

### 3. JSON 模式自愈(3 次)

走 structured output(`response_format=json_schema`)。若仍拿不到合法 JSON:
把模型上一轮回复 + 具体报错追加进对话再问一次,共 3 次(`JSON_MAX_ATTEMPTS`)。
usage 跨重试累加,`LLMResult.attempts` 记实际请求数(trace 里能看到"这次抽取重试过")。
校验刻意轻量(能解析成对象 + 顶层 required 齐全),字段级校验交给调用方的 Pydantic 模型。

### 4. 流式的 usage

`stream_options={"include_usage": True}`,usage 在**最后一个不带 choices 的 chunk** 上;
不开这个选项就统计不到 token。建流失败可重试;**流中途断了不重试**(已吐出的 token 收不回来)。
`stream()` 最后一定 yield 一个 `type="end"` 事件,带完整 `LLMResult`。

## 错误分类(retry.py)

| 供应商异常 | 处理 |
| --- | --- |
| `RateLimitError` / `APITimeoutError` / `APIConnectionError` / `InternalServerError` | 指数退避重试,共 `PROVIDER_MAX_ATTEMPTS` 次 |
| `AuthenticationError` / `PermissionDeniedError` | 立刻 `ConfigError(code=provider_auth_error)` —— 这是配置问题,不是"服务不可用" |
| 其他 `APIStatusError` / `OpenAIError` | `ProviderError`(502) |

key 完全没配(空/太短)由 `config.py` 的 `MissingConfigError` 在 import 期就拦住。

## 价格表(pricing.py)

单位美元 / 1M tokens,带日期后缀的快照名按最长前缀匹配。
未知型号返回 0 并告警一次 —— 价格表过期不能让问答链路挂掉。
`cost_usd` 量化到 6 位小数,对齐 `traces.cost_usd` 的 `numeric(10,6)`。

## 加一个新供应商要改哪

1. 新建 `<vendor>_llm.py`,实现 `LLMProvider` 的两个方法(不需要继承,Protocol 是结构化的)
2. `pricing.py` 补价格
3. `config.py` 的 `llm_provider` Literal 加取值 + 新供应商的 key 字段
4. `registry.py` 的 `get_llm()` 加分支
5. `.env.example` / `.env` 同步

## C7:cross-encoder 重排(S2 引入,2026-08-25)

`CrossEncoderReranker` 与 bi-encoder(embedding)的区别:query 与候选**拼在一起**过模型
(`[CLS] q [SEP] doc [SEP]`),交叉注意力直接输出相关性分数 —— **不能预计算**,
所以只用在召回之后的少量候选上。

**三个设计点**(全部有 Step 5 实测依据,见 `documents/S2-PLAN.md` 附录二):

1. **进程内,不单起容器**:30 条候选一次重排中位 **207ms**(本机 CPU),
   不值得为它多维护一个容器与一份 bootstrap 步骤。
2. **CPU 推理必须 `asyncio.to_thread`**:`model.predict()` 是阻塞的,
   直接 await 会把整个事件循环卡住 —— 一次重排就能拖垮全服务的并发。
3. 🩸 **`guard` 策略**:cross-encoder 偶尔会**整题失灵**,对所有候选都打负分,
   这时它的排序就是噪声(实测 c03:两条腿都排第 2 的切片被它打到第 11)。
   判据**不能用单条分数**(跨题不可比,实测正例最低 −11.11 / 负例最高 +2.61 重叠),
   而要用**整题最高分**:低于 `DOC_RAG_RERANK_GUARD`(−2.5)就原序返回。
   → 因此 `rerank()` 的 `docs` **必须按上游召回融合的名次传入**,原序返回才有意义。
   实测 90% → 95%。

🩸 **加载耗时的真相**(2026-08-25 实测拆解):

| 环节 | 联网核对版本 | `HF_HUB_OFFLINE=1` |
| --- | --- | --- |
| import torch/transformers/sentence_transformers | 3.2s | 2.5s |
| **读权重 + 建模型** | **8.6s** | **0.4s** |
| 首次 predict(计算图预热) | 1.4s | 0.1s |
| 合计 | **13.2s** | **3.1s** |

那 8.6 秒**不是在读盘**(权重才 90MB),是 `sentence-transformers` 每次加载都去
HuggingFace 核对版本的网络往返。默认 `doc_rag_rerank_offline=True`,
在 import 之前设 `HF_HUB_OFFLINE=1`(**必须在 import 前,HF 客户端在 import 期读它**)。
代价:权重要先下好 —— `bootstrap.sh` 第 8 步 / `make rerank-model`。

构造时用 daemon 线程后台预热;**预热只在第一次 `get_reranker()` 时才开始**,
所以这 3 秒仍落在第一个用户请求上。
✅ **决定不在 lifespan 里预热**(2026-08-25 需求方):3 秒可接受,
而加那一行的代价是**所有环境都常驻几百 MB**(只跑 S1/S3 的也要付)、CI 也会去加载模型。
—— 如果哪天加载时间又变长,或首问延迟成了演示问题,再回头加。
