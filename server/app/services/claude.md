# server/app/services/

**职责**:业务逻辑层,按知识域分包(路由只调这里,不在路由里写逻辑)。

| 文件/目录 | 说明 |
| --- | --- |
| `__init__.py` | **全局唯一的 Job 注册 import 点**(现注册 `core.jobs_demo` + S1 + S2 + S3) |
| `exact_qa/` | 精准问答域(S1,空壳),见 `exact_qa/claude.md` |
| `document/` | 文档 RAG 域(S2:解析 / 清洗 / 切分 / 图表描述 / 混合检索 / 发布),见 `document/claude.md` |
| `text2sql/` | 智能问数域(S3:语义层治理 / 模板生成 / 受约束改写 / 执行闸 / 检索),见 `text2sql/claude.md` |

**纪律**:域与域互不 import;只向上依赖 `app/core` / `app/models` / `app/schemas`。

详见 `architect.md`。
