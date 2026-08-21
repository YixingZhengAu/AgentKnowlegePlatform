# web/demo/

**职责**:静态预览版入口 —— 把前端打成一个**不需要后端**的自包含 HTML,给人看界面。

| 文件 | 说明 |
| --- | --- |
| `main.tsx` | 预览版入口:HashRouter + 把 `fetch` 换成读 fixtures + 右下角预览角标 |
| `fixtures.ts` | 固定响应(从真后端抓的实际返回;会话列表是手写演示数据) |
| `index.html` | 预览版 HTML 入口 |
| `inline.mjs` | 把构建产物拼成单文件 `dist-demo/preview.html` |

跑法:`make demo`(= `vite build --config vite.config.demo.ts` + `node demo/inline.mjs`)。
**这个目录不参与正式构建**;`src/` 一行都不为它改。详见 `architect.md`。
