# server/app/schemas/

**职责**:Pydantic 出入参模型;前端类型由 openapi 生成,所以这里的字段名就是契约。

| 文件 | 内容 |
| --- | --- |
| `common.py` | `ORMModel`(from_attributes)、`ListResponse[T]`、`HealthResponse` |
| `knowledge.py` | `KnowledgeBaseOut` |
| `agent.py` | `AgentOut` / `AgentDetailOut` / `AgentKbBindingOut` |
| `conversation.py` | `ConversationOut` / `MessageOut`(带 `citations` + `verified`:刷新后标注不能丢) |
| `chat.py` | `ChatRequest` / `ChatResponse` / **`MessageCitationOut` + `CitationExtra`**(引用的真 schema,前端不再手写)/ `TraceSpanOut` / `TraceOut` |
| `job.py` | `JobSubmitRequest` / `JobOut`(jsonb 字段保持宽松,结构由 Job 框架约定) |
| `exact_qa.py` | **S1 精准问答契约**:产物文件名/图片 URL 常量 + ContentBlock/ParseResult + OriginRef/QaCandidate + HitTier/RetrievalResult |
| `staging.py` | `StagingItemOut` / `StagingItemPatch` / `StagingBulkRequest` / `StagingSummary` / `PublishResult` |
| `document.py` | **S2 文档 RAG 契约**:落盘常量 + MineruBlock/Block/Chunk/Figure 三层 + `Chunk.as_payload()`(发布与合并都靠它往返)+ DocumentOut/UploadResult |
| `text2sql.py` | **S3 智能问数契约**:数据源(口令只进不出)/ Schema 治理 / 三区参数 `IntentParams` / 意图与模板 Run(`TemplateDesign` 跟着 `template.py` 的结构化输出走)/ 相似问法 / 空路由负例面 |

详见 `architect.md`。
