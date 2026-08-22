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

跑:`cd server && uv run pytest`(全部离线,不打真实 API、不连 DB)。
真实调用的验证在 `scripts/smoke_*`。

**S1 为什么只给这几个函数写单测**(S1-plan §7.1):它们输入输出确定,而且**改错了不报错、
只是静默给错答案** —— 沙箱阶段在这里踩过两次真坑,都是跑评测才发现的。其余靠冒烟脚本。

详见 `architect.md`。
