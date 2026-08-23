# web/scripts/

**职责**:前端冒烟脚本(Node 原生跑 TS,不进构建产物)。

| 文件 | 说明 |
| --- | --- |
| `smoke_sse.ts` | 用**产线代码** `src/api/sse.ts` 打真后端,断言协议不变量(meta 在前 / stage 成对 / done 唯一且在最后)|
| `ui_probe.mjs` | UI 走查底座:路由清单 + 用无头 Chrome 渲染 `dist-demo/preview.html`(被下面两个脚本 import)|
| `ui_inventory.mjs` | 交互清单基线/比对:视觉改版期间「只许改样子、不许改功能」的机器约束 |
| `ui_shot.mjs` | 按 Stage 出 1512×950 截图,供视觉验收并排比对 |

跑法(后端要先起):`make smoke-sse`,或 `cd web && npm run smoke:sse`。
换目标地址:`API_BASE=http://localhost:5173 npm run smoke:sse`(穿 Vite 代理跑一遍)。

UI 走查(先 `make demo`,不需要后端):
`node scripts/ui_inventory.mjs`(写基线)/ `--check`(比对,不一致退出码 1)/ `node scripts/ui_shot.mjs <stage>`。
产物都在仓库根的 `tmp/`(已 gitignore):`tmp/ui-baseline/*.json`、`tmp/ui-shots/<stage>/*.png`。

详见 `architect.md`。
