# web/src/pages/

**职责**:一页一文件。页面负责取数 + 组装组件,不写样式常量、不写 API 类型。
三类知识的 ingestion 页**不在这里**,在 `src/domains/<域>/`(结构调整,见 S0-PLAN §5)。

| 文件 | 数据来源 |
| --- | --- |
| `ChatPage.tsx` | `GET /api/agents` + `/api/conversations` + `useChat`(SSE);右侧挂 `<TracePanel>` |
| `AgentListPage.tsx` | `GET /api/agents` |
| `AgentDetailPage.tsx` | `GET /api/agents/{id}`(含 KB 绑定,按 priority 升序) |
| `ReviewPage.tsx` | `GET /api/jobs/{id}` + 探一条 `/api/staging`(定类型)→ `<StagingReview>`;路由 `/jobs/:jobId/review`,当前唯一入口是直链(旧任务列表页已删) |
| `SettingsPage.tsx` | `GET /healthz`(**任何密钥都不进前端**) |
| `StyleGuidePage.tsx` | 无后端依赖;隐藏路由 `/styleguide`,UI 验收对照页 |
| `how-it-works/` | 面试投屏用的说明页(`/how-it-works` 总页 + `/:layer` 子页),零后端依赖;见该目录 claude.md |

详见 `architect.md`。
