/** 静态预览版入口(`make demo`)—— 把前端打成一个不需要后端的单文件页面。
 *
 * 与正式入口 `src/main.tsx` 的两点区别,都只在这里,src 一行不改:
 *   1. 路由用 HashRouter:静态托管没有服务端 rewrite,刷新 /kbs 会 404
 *   2. fetch 被换成读 fixtures:同样的 client / hooks / 页面代码,只是数据来自固定响应
 * 于是这份预览页跑的确实是产线组件,不是另画的一套界面。
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'

import App from '@/App'
import '@/index.css'
import { FIXTURES } from './fixtures.ts'

const LATENCY_MS = 220 // 留一点延迟,骨架屏才看得见(真环境本地约 5–30ms)

globalThis.fetch = (async (input: RequestInfo | URL) => {
  const url = typeof input === 'string' ? input : input.toString()
  const path = url.replace(/^https?:\/\/[^/]+/, '')
  await new Promise((r) => setTimeout(r, LATENCY_MS))

  const body = FIXTURES[path]
  if (body === undefined) {
    // 没有 fixture 就返回真后端那套错误体格式,顺便证明前端的错误态是真在工作的
    return new Response(
      JSON.stringify({
        error: {
          code: 'not_available_in_preview',
          message: `This preview has no fixture for ${path}. Run the full stack for live data.`,
        },
      }),
      { status: 404, headers: { 'Content-Type': 'application/json' } },
    )
  }
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}) as typeof fetch

function PreviewBadge() {
  return (
    <div className="bg-card fixed bottom-4 left-4 z-50 flex items-center gap-2 rounded-full border px-3 py-1.5 shadow-[var(--shadow-pop)]">
      <span className="bg-accent size-2 rounded-full" />
      <span className="font-mono text-[11px]">static preview · fixture data</span>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <App />
      <PreviewBadge />
    </HashRouter>
  </StrictMode>,
)
