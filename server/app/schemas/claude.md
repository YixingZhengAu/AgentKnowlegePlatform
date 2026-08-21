# server/app/schemas/

**职责**:Pydantic 出入参模型;前端类型由 openapi 生成,所以这里的字段名就是契约。

| 文件 | 内容 |
| --- | --- |
| `common.py` | `ORMModel`(from_attributes)、`ListResponse[T]`、`HealthResponse` |
| `knowledge.py` | `KnowledgeBaseOut` |
| `agent.py` | `AgentOut` / `AgentDetailOut` / `AgentKbBindingOut` |
| `conversation.py` | `ConversationOut` / `MessageOut` |
| `chat.py` | `ChatRequest` / `ChatResponse` / `TraceSpanOut` / `TraceOut` |
| `job.py` | `JobSubmitRequest` / `JobOut`(jsonb 字段保持宽松,结构由 Job 框架约定) |

详见 `architect.md`。
