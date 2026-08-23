# web/scripts/architect.md

## smoke_sse.ts 为什么这么写

- **import 产线代码而不是复制解析逻辑**:要验的是 `src/api/sse.ts` 里那份帧解析与事件分派;
  抄一份到脚本里就等于验了个假的
- Node 24 原生跑 `.ts`(只做类型擦除),所以产线代码里不能出现 enum / namespace 这类
  不可擦除语法(`tsconfig` 已开 `erasableSyntaxOnly` 兜住),
  且相对 import 要带 `.ts` 后缀(Node 不做扩展名补全)
- 脚本里给 `globalThis.fetch` 打了一层前缀补全:产线代码用相对路径(浏览器里同源),
  Node 里没有 origin,所以把 `/api/...` 补成 `${API_BASE}/api/...`
- 断言的是协议的**不变量**,不是一条写死的事件串(S1 改过一次:链路前面插了
  `retrieve_exact_qa`,写死顺序的话每加一个 stage 这个脚本就红一次):
  ① meta 在最前(新会话的 id 必须先到)② `stage_start`/`stage_end` 成对,且第一个 token
  之前至少有过一个 stage ③ `done` 唯一且在最后;再加内容三件:至少一个 token、
  回答非空、`done.status === 'completed'` 且带 trace

## 两种跑法的区别

| 命令 | 验什么 |
| --- | --- |
| `npm run smoke:sse` | 直连 8000:后端 SSE 协议 + 前端解析 |
| `API_BASE=http://localhost:5173 npm run smoke:sse` | 穿 Vite 代理:**代理会不会把流缓冲住**(浏览器实际走这条路) |

## UI 走查三件套(ui_probe / ui_inventory / ui_shot)

为视觉改版(`tmp/UI-REDESIGN-PLAN.md`)建的自测闸门,与后端无关。

- **渲染对象是 `make demo` 的 `dist-demo/preview.html`**:fixture 数据、零后端、零外部请求,
  所以任何时候都能重放,截图也不会因为库里数据变了而漂
- **不走 Playwright MCP**:那个浏览器实例常被别的会话占着(`Browser is already in use`),
  直接调 Playwright 下载好的 `chrome-headless-shell` 二进制
- **preview.html 是 HTML 片段**,于是可以在它前后各夹一段脚本再写成临时页:
  前面设置 `location.hash` 选路由,后面放探针;`--virtual-time-budget` 把 setTimeout 快进掉,
  「等 7 秒」实际只花几百毫秒。虚拟时间轴:0 选路由 → 5s 跑 `route.prep` → 7s 取数/截图
- **`route.prep`** 是在页内跑的一小段 JS,用来把「交互后才存在的形态」也纳入基线
  (目前只有一处:收起右侧面板,好让 Hide/Show 两种文案都被盯住)
- **`ui_inventory.mjs` 抓两样**:① 按 DOM 顺序的可交互元素(tag/role/type/可访问文本/disabled/href)
  ② 结构计数(tr/li/table/form/label)。第二样是补漏的 —— 列表行做成 `<tr onClick>`(Agents 列表)
  时它不是按钮,光看可交互元素会漏掉「行少了一条」
- 比对用**逐位置 diff** 而不是整份 JSON diff:改版期一次只想看见那几条差异
