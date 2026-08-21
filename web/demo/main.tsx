/** 静态预览版入口(`make demo`)—— 把前端打成一个不需要后端的单文件页面。
 *
 * 与正式入口 `src/main.tsx` 的两点区别,都只在这里,src 一行不改:
 *   1. 路由用 HashRouter:静态托管没有服务端 rewrite,刷新 /kbs 会 404
 *   2. fetch 被换成读 fixtures:同样的 client / hooks / 页面代码,只是数据来自固定响应
 * 于是这份预览页跑的确实是产线组件,不是另画的一套界面。
 *
 * **对话是真的在流**:chat 接口返回一个 ReadableStream,按 SSE 协议一帧一帧地推,
 * 由产线的 `src/api/sse.ts` 解析。所以预览里的打字机效果、stage 事件、轨迹面板
 * 走的都是真代码路径,只有内容是写死的(问什么都答同一段)。
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'

import App from '@/App'
import '@/index.css'
import { DEMO_JOB_ID, FIXTURES, STAGING_ITEMS } from './fixtures.ts'

const LATENCY_MS = 220 // 留一点延迟,骨架屏才看得见(真环境本地约 5–30ms)

const CHAT_PATH = /^\/api\/agents\/[^/]+\/chat$/
// 预览里的固定回答(演示的是流式渲染与轨迹面板,不是模型能力)
const CANNED_ANSWER =
  'The PV-ezRack SolarRoof carries a 15 year structural warranty when it is installed to the ' +
  'published torque and span tables. Anodised aluminium components are covered for corrosion ' +
  'for the same period; stainless fasteners are covered for 10 years.'

const frame = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`

/** 按真事件协议推一条流(出处 server/app/api/chat.py)。 */
function cannedStream(): Response {
  const enc = new TextEncoder()
  const messageId = 'c4d5e6f7-0001-4a10-9f01-bbbb00000001'
  const span = {
    stage: 'generate',
    seq: 1,
    status: 'ok',
    latency_ms: 2417,
    model: 'gpt-5',
    usage: { prompt_tokens: 218, completion_tokens: 61, total_tokens: 279 },
    cost_usd: '0.001913',
    error: null,
  }
  const words = CANNED_ANSWER.split(' ')
  const stream = new ReadableStream({
    async start(c) {
      const push = (e: string, d: unknown) => c.enqueue(enc.encode(frame(e, d)))
      const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))
      push('meta', {
        message_id: messageId,
        conversation_id: '3f2b1c88-0001-4a10-9f01-aaaa00000001',
      })
      push('stage_start', { stage: 'generate' })
      await wait(600)
      for (const w of words) {
        push('token', { text: w + ' ' })
        await wait(35)
      }
      push('stage_end', span)
      push('done', {
        message_id: messageId,
        conversation_id: '3f2b1c88-0001-4a10-9f01-aaaa00000001',
        status: 'completed',
        usage: span.usage,
        cost_usd: span.cost_usd,
        latency_ms: span.latency_ms,
        citations: [],
        trace: [span],
        error: null,
      })
      c.close()
    },
  })
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

/** 审核台的内存库:预览里 PATCH / 批量 / 发布真的改数据,所以筛选计数、发布按钮都跟着动。
 *  只有这一块需要"可写",因为审核这件事的全部意义就是状态会变。 */
function stagingRoutes(path: string, method: string, init?: RequestInit): Response | null {
  const url = new URL(path, 'http://x')
  const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {}
  const stamp = () => new Date().toISOString()

  if (method === 'GET' && url.pathname === '/api/staging') {
    const status = url.searchParams.get('review_status')
    const sort = url.searchParams.get('sort') ?? 'confidence_asc'
    let items = STAGING_ITEMS.filter((i) => !status || i.review_status === status)
    if (sort === 'confidence_asc') items = [...items].sort((a, b) => a.confidence - b.confidence)
    if (sort === 'confidence_desc') items = [...items].sort((a, b) => b.confidence - a.confidence)
    const limit = Number(url.searchParams.get('limit') ?? 200)
    return json({ items: items.slice(0, limit), total: Math.min(items.length, limit) })
  }

  if (method === 'GET' && url.pathname === '/api/staging/summary') {
    const count = (s: string) => STAGING_ITEMS.filter((i) => i.review_status === s).length
    return json({
      total: STAGING_ITEMS.length,
      pending: count('pending'),
      approved: count('approved'),
      modified: count('modified'),
      rejected: count('rejected'),
      published: STAGING_ITEMS.filter((i) => i.published).length,
    })
  }

  if (method === 'PATCH' && url.pathname.startsWith('/api/staging/')) {
    const item = STAGING_ITEMS.find((i) => i.id === url.pathname.split('/').pop())
    if (!item) return null
    if (body.payload) item.payload = { ...item.payload, ...(body.payload as object) }
    // 状态推导与后端一致(core/staging.py::derive_review_status):改了内容没表态 = modified
    item.review_status =
      (body.review_status as string) ?? (body.payload ? 'modified' : item.review_status)
    item.reviewed_at = stamp()
    return json(item)
  }

  if (method === 'POST' && url.pathname === '/api/staging/bulk') {
    const ids = new Set(body.ids as string[])
    let updated = 0
    for (const item of STAGING_ITEMS) {
      if (!ids.has(item.id) || item.published) continue
      item.review_status = body.review_status as string
      item.reviewed_at = stamp()
      updated++
    }
    return json({ updated })
  }

  if (method === 'POST' && /^\/api\/jobs\/[^/]+\/publish$/.test(url.pathname)) {
    const publishable = STAGING_ITEMS.filter(
      (i) => ['approved', 'modified'].includes(i.review_status) && !i.published,
    )
    if (!publishable.length) {
      return new Response(
        JSON.stringify({
          error: { code: 'nothing_to_publish', message: 'Approve at least one item first.' },
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } },
      )
    }
    for (const i of publishable) i.published = true
    const job = FIXTURES[`/api/jobs/${DEMO_JOB_ID}`] as Record<string, unknown>
    job.status = 'published'
    job.stats = { staged: STAGING_ITEMS.length, published: publishable.length }
    return json({
      record_id: 'f3000000-0001-4a10-9f01-ffff00000001',
      job_id: DEMO_JOB_ID,
      job_status: 'published',
      published: publishable.length,
      item_counts: { published: publishable.length },
      created_at: stamp(),
    })
  }
  return null
}

globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === 'string' ? input : input.toString()
  const path = url.replace(/^https?:\/\/[^/]+/, '')
  const method = (init?.method ?? 'GET').toUpperCase()
  await new Promise((r) => setTimeout(r, LATENCY_MS))

  if (CHAT_PATH.test(path)) return cannedStream()
  const staged = stagingRoutes(path, method, init)
  if (staged) return staged
  // 写操作在预览里没有后端可写:提交任务回放那条跑完的任务,删除会话直接 204
  if (method === 'POST' && path === '/api/jobs') return json(FIXTURES[DEMO_JOB])
  if (method === 'POST' && path.endsWith('/retry')) return json(FIXTURES[DEMO_JOB])
  if (method === 'DELETE') return new Response(null, { status: 204 })

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
  return json(body)
}) as typeof fetch

const DEMO_JOB = '/api/jobs/e1000000-0001-4a10-9f01-dddd00000001'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

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
