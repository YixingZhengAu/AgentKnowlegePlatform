# server/app/api/

**职责**:HTTP 路由。只做参数校验 + 调用 + 组装出参,不写业务逻辑。

| 文件 | 路由 |
| --- | --- |
| `__init__.py` | `api_router`:所有子路由挂载点(新增路由文件要在这里 include) |
| `deps.py` | `SessionDep`、`CurrentUser`(S0–S5 硬编码 default_user) |
| `health.py` | `GET /healthz`(含 DB 连通检查) |
| `kbs.py` | `GET /api/kbs`、`GET /api/kbs/{kb_id}` |
| `agents.py` | `GET /api/agents`、`GET /api/agents/{agent_id}`(带 KB 绑定) |
| `conversations.py` | `GET /api/conversations`、`GET .../{id}/messages`、`DELETE .../{id}`(软删) |
| `chat.py` | `POST /api/agents/{agent_id}/chat`(SSE 流式 / 非流式二合一) |
| `traces.py` | `GET /api/traces/{message_id}`(一次问答的全部 stage) |
| `jobs.py` | `GET/POST /api/jobs`、`GET /api/jobs/types`、`GET /api/jobs/{id}`、`POST /api/jobs/{id}/retry` |

详见 `architect.md`(含 SSE 事件协议)。
