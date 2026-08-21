# web/

**职责**:React + TypeScript + Vite 前端(三栏工作台)。界面文案一律英文(D5),无 i18n。

视觉规范唯一出处:`documents/UI-STYLE.md`;**色值只允许写在 `src/index.css` 的品牌层**。
API 类型唯一来源:`make types` 生成的 `src/api/types.gen.ts`,**禁止手写 API 类型**;
它是生成物,**合并冲突永远重跑 `make types` 解决,禁止手工合并**。

**并行开发纪律**:`src/{api,components,layouts,lib}` 是 shared 层,域开发者只读;
域代码只落在 `src/domains/<域>/`;要改公共契约(shared 层 / SSE 协议 / 渲染器接口)单独提。

| 路径 | 说明 |
| --- | --- |
| `src/` | 应用代码,见 `src/claude.md` |
| `scripts/` | 前端冒烟脚本(SSE 客户端打真后端),见 `scripts/claude.md` |
| `demo/` | 静态预览版入口(fixture 数据、零后端),见 `demo/claude.md` |
| `openapi.json` / `src/api/types.gen.ts` | 生成物,不手改 |
| `index.html` / `vite.config.ts` | 入口与 dev 代理(`/api`、`/healthz` → 8000) |
| `vite.config.demo.ts` | 静态预览版的构建配置(`make demo`) |
| `components.json` | shadcn/ui CLI 配置(`npx shadcn add <x>` 会按它落文件) |
| `eslint.config.js` / `.prettierrc` | 代码规范(`npm run lint` / `make lint`) |

常用命令:`make dev`(前后端一起起)/ `make types`(契约)/ `make lint` / `make smoke-sse` / `make demo`。

详见 `architect.md`。
