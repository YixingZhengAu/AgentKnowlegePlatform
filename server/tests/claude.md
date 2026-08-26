# server/tests/

**职责**:pytest 测试(pytest + pytest-asyncio,`asyncio_mode = "auto"`,不用挂 marker)。

| 文件 | 覆盖 |
| --- | --- |
| `test_providers.py` | Protocol 一致性、单例、价格换算、JSON 轻量校验、透传 rerank |
| `test_trace.py` | `traced()` 计时/异常记录、seq 递增、`summarize()` 截断、用量汇总 |
| `test_jobs.py` | Job 注册表、步骤声明、`step_<name>` 约定分发、假任务 payload 形状 |
| `test_staging.py` | payload 浅合并语义、审核状态推导、状态计数、`qa_pair` publisher 在册 |
| `test_exact_qa_matching.py` | ★ 区分性 token 保险:ResNet-101/152 判重坑、416×416 高分误命中、护栏能力边界 |
| `test_exact_qa_retriever.py` | 命中分档边界(0.55/0.40 闭区间、最低正例 0.613、护栏只降级不升级) |
| `test_exact_qa_extractor.py` | quote 逐字定位与前缀修复、五种硬约束丢弃、页码以块为准 |
| `test_exact_qa_similar.py` | 相似问两道过滤(与标准问相同 / 跨条冲突 / 已接受改写也进问题面) |
| `test_doc_rag_citations.py` | ★ 引用的**编号对齐**(prompt 的 `[n]` ≡ `citations.seq`)与**入选规则**(只挂正文引过的 / 哨兵句零引用 / 忘标编号保底 Top-1 / 越界编号丢掉)—— 两种错法都不报错,只是安静做错
| `test_doc_rag_verify.py` | 生成后校验的**失败纪律**:它跑在落库之前,里面出任何事都只能安静返回空报告 —— 否则一次已经答完的问答连消息带 trace 一起丢
| `test_document_operations.py` | S2-4 运营层的两处静默错法:退休行 `seq` 编解码互逆(含 `seq=0` 边界)+ embedding 输入拼法在「发布」与「重新启用」上一致
| `test_document_parser.py` | S2 块类型宽容度 + **标题路径**(兄弟标题不许变父子、跳级不错位)+ 图表线索不丢 |
| `test_document_chunker.py` | ★ S2 质量地基:句子边界不腰斩、URL 不被冒号切碎、中文拼接不插空格、code 保换行、无纯标题片、payload 往返 |
| `test_document_retriever.py` | S2 停用词处理(AND 语义 + `simple` 不去停用词这两个坑)+ RRF 只吃名次 |
| `test_exact_qa_parser.py` | ★ 块类型宽容度回归:header/footer 不许打死整篇解析 + 拼 md 只渲染内容块 + 丢弃按类型计数(S1-PLAN §9.1) |

跑:`cd server && uv run pytest`(全部离线,不打真实 API、不连 DB)。
真实调用的验证在 `scripts/smoke_*`。

**S1 为什么只给这几个函数写单测**(S1-plan §7.1):它们输入输出确定,而且**改错了不报错、
只是静默给错答案** —— 沙箱阶段在这里踩过两次真坑,都是跑评测才发现的。其余靠冒烟脚本。

详见 `architect.md`。
