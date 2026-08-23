# server/scripts/

**职责**:CLI 脚本。六步法的第 ② 步(先在命令行把逻辑跑通,再接 HTTP)都写在这里。

| 文件 | 用途 |
| --- | --- |
| `seed_minimal.py` | 灌最小数据:default_user + 3 个空 KB + 默认 Agent + 绑定(幂等) |
| `dump_openapi.py` | 导出 openapi.json(`make types` 的第一步) |
| `smoke_llm.py` | LLM 冒烟:补全 + 流式 + JSON 模式(`make smoke`) |
| `smoke_embedding.py` | Embedding 冒烟:维度 + 余弦相似度(`make smoke`) |
| `smoke_exact_qa.py` | S1 三个 LLM 调用点(抽取 / 相似问 / 命中复核)真调一次 + **复核关取向用例表**(简略/含糊的正确答案必须放行) |
| `smoke_exact_qa_store.py` | S1 存储层:采纳事务 + **pgvector 分数与手算余弦对数(1e-3)** + 下线 |
| `smoke_s1_api.sh` | S1 HTTP 全链路 15 步(上传→解析→校对→抽取→采纳→正式 QA→**删文档**),含反例断言 |
| `smoke_s1_chat.py` | S1 问答三问(正例/越界/困难负例)+ SSE 协议 + **历史消息读回来标注还在** |
| `verify_bizdb.py` | 演示业务库 27 项数据断言(行数/对账/日期覆盖/库存流水/**只读账号写入被拒**),`make bizdb-verify` |
| `seed_s3_demo.py` | 灌 S3 演示知识:数据源(连接串加密)+ 语义层 + 7 个已验证意图 + 索引面,`make seed-s3`(幂等) |
| `smoke_s3_index.py` | S3 索引层:**pgvector 余弦 vs 手算点积对数(1e-6)** + 留一法审计 + 空路由回归 |
| `smoke_s3_e2e.py` | S3 全链路:B8 冻结的 20 题评测集(`--check` 零 LLM / `--all` 真调 / `--question` 单问)—— **"迁移无损"的唯一证据** |
| `smoke_s3_api.sh` | S3 HTTP 层 27 步(数据源/治理/意图/Run/发布);**一半的价值在错误路径**,且**不留痕**(临时资产删掉、下线的重新发布、索引面回到原数),`make smoke-s3-api` |
| `smoke_s3_chat.py` | S3 问数接进 chat 的三问(命中 / 模板外 / 非问数)+ trace 五要素 + 零 LLM 记账断言 + **拒答文案必须等于 planner 的 `infeasible_reason`** + SSE 协议,`make smoke-s3-chat` |

`fixtures/` 是冒烟脚本与手动演示的输入文件:

| 文件 | 用途 |
| --- | --- |
| `sample-paper-3p.pdf` | `smoke_s1_api.sh` 的上传输入(YOLOv3 论文前 3 页:图/表/公式齐全) |
| `qa_with_similar.json` | `smoke_exact_qa_store.py` 的候选集(36 条 / 180 个索引面),免得每次先花钱跑抽取 |
| `clenergy-handbook.{html,pdf}` | 手动演示用的 Clenergy 业务手册(虚构内容,html 是可再生成的源) |
| `s3/` | S3 的**已评审治理资产**(语义层 / 7 个意图的模板与参数区 / 相似问法 / 空路由负例面 / 评测集 / 已存改写计划);`seed_s3_demo.py` 与 `smoke_s3_e2e.py` 读它。**不是测试数据**,见该目录 README |

详见 `architect.md`。
