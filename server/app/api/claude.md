# server/app/api/

**职责**:HTTP 路由。只做参数校验 + 调用 + 组装出参,不写业务逻辑。

| 文件 | 路由 |
| --- | --- |
| `__init__.py` | `api_router`:所有子路由挂载点(新增路由文件要在这里 include) |
| `deps.py` | `SessionDep`、`CurrentUser`(S0–S5 硬编码 default_user) |
| `health.py` | `GET /healthz`(含 DB 连通检查) |
| `kbs.py` | `GET /api/kbs`、`GET /api/kbs/{kb_id}` |
| `agents.py` | `GET /api/agents`、`GET /api/agents/{agent_id}`(带 KB 绑定) |
| `conversations.py` | `GET /api/conversations`、`GET .../{id}/messages`(**带 citations + verified**)、`DELETE .../{id}`(软删) |
| `chat.py` | `POST /api/agents/{agent_id}/chat`(SSE 流式 / 非流式二合一) |
| `traces.py` | `GET /api/traces/{message_id}`(一次问答的全部 stage) |
| `jobs.py` | `GET/POST /api/jobs`、`GET /api/jobs/types`、`GET /api/jobs/{id}`、`POST /api/jobs/{id}/retry`、`POST /api/jobs/{id}/publish` |
| `staging.py` | `GET /api/staging`、`GET /api/staging/summary`、`PATCH /api/staging/{id}`、`POST /api/staging/bulk` |
| `exact_qa.py` | **S1 域接口**:上传/文档列表/**删文档**、校对文本读写、确认抽取、采纳/不采纳、正式 QA 管理 |
| `document.py` | **S2 域接口**:上传 PDF(启 `doc_ingest`)/ 文档列表与详情 / 删文档 / 合并相邻切片 / `GET /chunks/{id}` 引用回显取全文 / **运营(S2-4)**:切片列表 · 禁用 · 启用 · 单文档重跑 / `GET /search` 检索调试台 |
| `text2sql.py` | **S3 域接口**:数据源 CRUD/测连/同步、Schema 治理读写、AI 三件套(批量走 Job、单点同步)、意图与模板 Run、相似问法、空路由负例面、发布/下线 |
| `files.py` | `GET /api/files/parses/{document_id}/images/{name}`(图片出口,M1.5)、`GET /api/files/documents/{id}/pdf`(原件) |

详见 `architect.md`(含 SSE 事件协议)。
