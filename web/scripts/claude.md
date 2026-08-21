# web/scripts/

**职责**:前端冒烟脚本(Node 原生跑 TS,不进构建产物)。

| 文件 | 说明 |
| --- | --- |
| `smoke_sse.ts` | 用**产线代码** `src/api/sse.ts` 打真后端,断言事件顺序与 done 终止 |

跑法(后端要先起):`make smoke-sse`,或 `cd web && npm run smoke:sse`。
换目标地址:`API_BASE=http://localhost:5173 npm run smoke:sse`(穿 Vite 代理跑一遍)。

详见 `architect.md`。
