# web/demo/architect.md

## 为什么要有它

界面要给人看(面试、评审、发链接),但真页面依赖后端 + 数据库 + LLM key。
所以留一条"只换数据源、不换代码"的旁路:**跑的是产线组件本身**,
不是另画一套静态页 —— 否则预览好看而真页面走样,就白搭了。

## 与正式入口的差异(全部集中在 main.tsx)

| | `src/main.tsx` | `demo/main.tsx` |
| --- | --- | --- |
| 路由 | `BrowserRouter` | `HashRouter`(静态托管没有 rewrite,刷新 `/kbs` 会 404) |
| 数据 | 真 fetch → Vite 代理 → 后端 | `globalThis.fetch` 换成读 `FIXTURES` |
| 对话 | 真 SSE 流 | `cannedStream()`:一个按真协议推帧的 ReadableStream |
| 写操作 | 真 POST / DELETE | 提交任务回放那条跑完的任务;DELETE 直接 204 |
| 标识 | 无 | 右下角 `static preview · fixture data` 角标 |

`App.tsx` / `layouts` / `pages` / `api` 一行不改。fixture 里没有的路径会返回后端那套错误体
(`code=not_available_in_preview`),所以错误态与 toast 在预览里也是真在工作的。

**对话是真的在流**:`cannedStream()` 返回的是 ReadableStream,按
`meta → stage_start → token* → stage_end → done` 一帧一帧推,由**产线的
`src/api/sse.ts`** 解析。所以预览里的打字机效果、阶段事件、轨迹面板走的都是真代码路径,
只有内容写死(问什么都答同一段)。这也顺便证明了 SSE 客户端不依赖真后端。

## 审核台在预览里是"可写"的

`main.tsx` 的 `stagingRoutes()` 把 `fixtures.ts` 的 `STAGING_ITEMS` 数组当内存库:
`GET /api/staging`(筛选 + 排序)、`GET /api/staging/summary`(现算计数)、
`PATCH`、`POST /api/staging/bulk`、`POST /api/jobs/{id}/publish` 全部真的改这个数组。

为什么只有这一块需要可写:**审核这件事的全部意义就是状态会变**。
如果通过一条之后计数不动、发布按钮不动,预览看起来就是坏的。
状态推导规则(只改内容 = `modified`)照抄后端 `core/staging.py::derive_review_status`,
两边不一致的话预览会教出错的直觉。

注意:只改 URL 的 hash **不会重新加载文档**,所以内存库里的改动会留着 ——
测预览时要硬刷新(`Page.reload`)才回到初始的 20 条 pending。

## 构建两步

```
vite build --config vite.config.demo.ts   # 入口 demo/,assetsInlineLimit 拉满 -> 字体转 data URI
node demo/inline.mjs                      # CSS + JS 内联进一个 HTML 片段
  └─ dist-demo/preview.html   ~700KB,零外部请求
```

产物是**片段**(只有 `<title>` + `<style>` + `#root` + `<script>`),没有 `<html>/<head>/<body>`:
既能直接静态托管,也能交给"外壳由平台包"的托管方式。

## inline.mjs 里两处必须做的转义

1. `</script` → `<\/script`:内联脚本里出现它会提前闭合标签
2. **非 ASCII 转 `\uXXXX`**:片段里没法声明 `<meta charset>`,
   托管方按别的编码解就会把 `·` 显示成 `Â·`(踩过,角标上直接能看到)

## 字体子集

`src/index.css` 只 import fontsource 的 **latin 子集**(界面英文单语):
西里尔/希腊/越南文子集会白占 1.2MB —— 内联字体时这条直接决定预览页是 700KB 还是 1.9MB。
