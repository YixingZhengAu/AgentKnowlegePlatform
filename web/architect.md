# web/architect.md

## 契约链路(Step 6 已跑通)

```
后端改 schema → make types → web/openapi.json → src/api/types.gen.ts → 前端编译报错
```

`make types` = `server/scripts/dump_openapi.py` 导出 + `openapi-typescript` 生成。
**验收实测**(Step 6 历史记录):把 `KnowledgeBaseOut.description` 改名后跑 `make types`,
`tsc -b` 报 `TS2339: Property 'description' does not exist`(当时直指 KbListPage 第 52 行;
该页已在结构调整中删除,链路不变 —— 如今报错会落在其他消费该类型的文件上)。

页面不直接引 `types.gen.ts` 的深路径,统一走 `src/api/schema.ts` 里的别名
(`KnowledgeBase` / `AgentDetail` / `ChatResponse` …),这样生成物结构变了只改一处。

## 目录与职责

| 目录 | 放什么 |
| --- | --- |
| `src/api/` | client(fetch + 错误翻译)、hooks(取数三态)、sse(流式协议)、schema(类型别名) |
| `src/components/` | 业务无关的通用件;`ui/` 是 shadcn 风格的原子件 |
| `src/layouts/` | `AppLayout`:三栏骨架 + 右侧面板插槽 |
| `src/pages/` | 一页一文件;`StyleGuidePage` 是 UI 验收对照页 |
| `src/lib/` | 无 React 依赖的工具:`utils`(cn)、`format`(en-AU)、`toast`(store) |
| `scripts/` | `smoke_sse.ts`:Node 直接跑产线 SSE 客户端打真后端 |

## 样式的三层结构(重要)

`src/index.css` 一个文件里分三层,组件只认第 2 层:

1. **品牌原色** `--brand-navy` / `--brand-yellow` …:从官网抓来的事实。**全仓库唯一允许出现 hex 的地方**
2. **语义变量** `--primary` / `--accent` / `--muted-foreground` …:shadcn/ui 的命名,指向第 1 层
3. **Tailwind** `@theme inline`:把第 2 层暴露成 `bg-primary` / `text-muted-foreground` 等工具类

**与 UI-STYLE §5.1 的差异**:Tailwind v4 用 CSS 里的 `@theme` 取代了 v3 的
`tailwind.config.js` 的 `theme.extend`,所以"CSS 变量 + theme.extend"在这里合成同一个文件,
仓库里没有 `tailwind.config.js`。

命名坑:`text-primary` 在 Tailwind 里是"主色文字",而 UI-STYLE 表格里的 `text-primary`
指正文色。所以正文色叫 `--foreground`(`text-foreground`),主色只用于 `bg-primary` 一类场景。

例外:侧栏的白色半透明叠加用 Tailwind 自带的 `bg-white/8`(UI-STYLE §3 指定的
`rgba(255,255,255,0.08)`)—— 那是叠加层不是品牌色,不进 token。

## 数据流

```
页面 useApi('/api/kbs')            src/api/hooks.ts
  └─ apiFetch                      src/api/client.ts:拼 API_BASE、解析后端错误体
       ├─ 成功 → {data, loading:false}
       └─ 失败 → ApiError{code,message} → pushToast('error', code, message) → <Toaster/>
```

- `loading` 是**推导**出来的(`已装载的 key !== 当前 key`),不在 effect 里 `setLoading(true)`。
  新版 `eslint-plugin-react-hooks` 会把"effect 里同步 setState"直接判 error(踩过)。
- `API_BASE` 默认空字符串:开发时走 Vite 代理同源,所以没有 CORS 预检,SSE 也不受影响。

## SSE 客户端(src/api/sse.ts)

不用 `EventSource`:它只能 GET、不能带 body。所以 `fetch` + `ReadableStream` 自己解帧。

- `parseSseFrame()` 单独导出,便于单点排查;帧分隔符按 `\r?\n\r?\n` 认(过代理可能被改写)
- 依赖后端三条保证(出处 `server/app/api/architect.md`):`done` 是唯一终止信号 /
  失败兜底话术也走 `token` / 流一开始状态码就定死 200
- **未知事件类型直接忽略** —— S1–S4 会加新事件(route、retrieve_*),老页面不能因此崩
- 收不到 `done` 就断流会抛 `stream_incomplete`,不允许"静默当成功"

## 右侧面板插槽(AppLayout)

页面调 `useRightPanel(title, node)` 把内容塞进右栏,卸载自动清空;没有内容时整栏不占宽度
(列表页不会白让 360px)。目前 `/chat` 用它放执行轨迹面板(旧 `/jobs` 任务页已删,
`<JobProgress>` 组件保留,由各域的摄取页面复用)。

## 已验证(Step 6–7)

- `tsc -b` / `npm run lint` / `npm run build` 全绿;`make dev` 一条命令起 8000 + 5173
- 只读路由用 headless Chrome dump DOM 断言过内容(3 个 KB、1 个 agent、health 1536)
- `npm run smoke:sse` 直连 8000 与穿 Vite 代理各跑一次:事件顺序、token 拼接、done 终止均正确
- 交互路径用 CDP(Node 自带 WebSocket,不装 puppeteer)真点按钮验过:
  发消息 → 流式 → 轨迹面板;点历史消息 → 展开看 prompt;Stop → interrupted;
  提交假任务 → 进度条走完;注入失败 → 从失败步骤重跑 → 跑完
