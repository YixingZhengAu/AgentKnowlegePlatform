# web/

**职责**:React + TypeScript + Vite 前端。

**当前只有生成物 `openapi.json` —— Step 6 才脚手架化。**

视觉规范唯一出处:`documents/UI-STYLE.md`(Clenergy 官网风:navy #00205B + 黄 #FFCB02 强调)。
界面文案与问答交互一律英文(D5),无 i18n。

| 路径 | 说明 |
| --- | --- |
| `openapi.json` | 由 `make types` 从后端导出(生成物,不手改) |
| `src/api/` | fetch 封装 + `types.gen.ts`(自动生成,**禁止手写 API 类型**) |
| `src/components/` | 通用组件(审核台 `<StagingReview>` 在这) |
| `src/layouts/` | 三栏布局 |
| `src/pages/` | chat / kb / agent / settings |

详见 `architect.md`。
