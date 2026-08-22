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

`fixtures/` 是冒烟脚本与手动演示的输入文件:

| 文件 | 用途 |
| --- | --- |
| `sample-paper-3p.pdf` | `smoke_s1_api.sh` 的上传输入(YOLOv3 论文前 3 页:图/表/公式齐全) |
| `qa_with_similar.json` | `smoke_exact_qa_store.py` 的候选集(36 条 / 180 个索引面),免得每次先花钱跑抽取 |
| `clenergy-handbook.{html,pdf}` | 手动演示用的 Clenergy 业务手册(虚构内容,html 是可再生成的源) |

详见 `architect.md`。
