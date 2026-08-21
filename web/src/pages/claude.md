# web/src/pages/

**职责**:一页一文件。页面负责取数 + 组装组件,不写样式常量、不写 API 类型。

| 文件 | 数据来源 |
| --- | --- |
| `ChatPage.tsx` | `GET /api/conversations`;并占住右侧执行轨迹面板(Step 7 填真内容) |
| `KbListPage.tsx` | `GET /api/kbs` |
| `AgentListPage.tsx` | `GET /api/agents` |
| `AgentDetailPage.tsx` | `GET /api/agents/{id}`(含 KB 绑定,按 priority 升序) |
| `SettingsPage.tsx` | `GET /healthz`(**任何密钥都不进前端**) |
| `StyleGuidePage.tsx` | 无后端依赖;隐藏路由 `/styleguide`,UI 验收对照页 |

详见 `architect.md`。
