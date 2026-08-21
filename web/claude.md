# web/

**职责**:React + TypeScript + Vite 前端(三栏工作台)。界面文案一律英文(D5),无 i18n。

视觉规范唯一出处:`documents/UI-STYLE.md`;**色值只允许写在 `src/index.css` 的品牌层**。
API 类型唯一来源:`make types` 生成的 `src/api/types.gen.ts`,**禁止手写 API 类型**。

| 路径 | 说明 |
| --- | --- |
| `src/` | 应用代码,见 `src/claude.md` |
| `scripts/` | 前端冒烟脚本(SSE 客户端打真后端),见 `scripts/claude.md` |
| `openapi.json` / `src/api/types.gen.ts` | 生成物,不手改 |
| `index.html` / `vite.config.ts` | 入口与 dev 代理(`/api`、`/healthz` → 8000) |
| `components.json` | shadcn/ui CLI 配置(`npx shadcn add <x>` 会按它落文件) |
| `eslint.config.js` / `.prettierrc` | 代码规范(`npm run lint` / `make lint`) |

常用命令:`make dev`(前后端一起起)/ `make types`(契约)/ `make lint` / `make smoke-sse`。

详见 `architect.md`。
