/** 前端 SSE 客户端冒烟:拿真后端跑 src/api/sse.ts 里那份解析器。
 *
 * 为什么不写单测:要验的是"帧怎么切、事件顺序对不对",而这两件事只有真流才说得清。
 * 所以这里 import 的是产线代码本身(不是复制一份解析逻辑),Node 24 直接跑 .ts。
 *
 * 跑法(后端要先起着,make api):
 *   cd web && npm run smoke:sse
 */

import { streamChat } from '../src/api/sse.ts'

const BASE = process.env.API_BASE ?? 'http://localhost:8000'
const QUESTION = process.env.QUESTION ?? 'Reply with exactly: SSE OK'

function line(label: string, detail: string) {
  console.log(`  ${label.padEnd(14)} ${detail}`)
}

async function main() {
  // sse.ts 用相对路径 + 同源(浏览器里走 Vite 代理),Node 里没有 origin,所以补一个 base
  const realFetch = globalThis.fetch
  globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) =>
    realFetch(
      typeof input === 'string' && input.startsWith('/') ? BASE + input : input,
      init,
    )) as typeof fetch

  const agents = (await realFetch(`${BASE}/api/agents`).then((r) => r.json())) as {
    items: { id: string; name: string }[]
  }
  const agent = agents.items[0]
  if (!agent) throw new Error('没有 agent,先跑 make seed')
  console.log(`[smoke_sse] agent = ${agent.name} (${agent.id})`)

  const order: string[] = []
  let tokens = 0
  let text = ''
  let firstTokenMs: number | null = null
  const t0 = Date.now()

  const done = await streamChat({
    agentId: agent.id,
    question: QUESTION,
    handlers: {
      onMeta: (d) => {
        order.push('meta')
        line(
          'meta',
          `message_id=${d.message_id.slice(0, 8)}… conversation_id=${d.conversation_id.slice(0, 8)}…`,
        )
      },
      onStageStart: (d) => {
        order.push('stage_start')
        line('stage_start', d.stage)
      },
      onToken: (t) => {
        if (firstTokenMs === null) {
          firstTokenMs = Date.now() - t0
          order.push('token')
        }
        tokens += 1
        text += t
      },
      onStageEnd: (s) => {
        order.push('stage_end')
        line(
          'stage_end',
          `${s.stage} status=${s.status} latency=${s.latency_ms}ms model=${s.model}`,
        )
      },
      onError: (e) => {
        order.push('error')
        line('error', `${e.stage ?? '-'}: ${e.message}`)
      },
      onDone: () => order.push('done'),
    },
  })

  line('tokens', `${tokens} chunks, first_token=${firstTokenMs}ms`)
  line('text', JSON.stringify(text.length > 80 ? text.slice(0, 80) + '…' : text))
  line('done', `status=${done.status} cost=${done.cost_usd} trace=${done.trace.length} stage(s)`)

  // 断言:顺序、内容、终止信号
  const expected = ['meta', 'stage_start', 'token', 'stage_end', 'done']
  if (order.join(' -> ') !== expected.join(' -> ')) {
    throw new Error(`事件顺序不对:${order.join(' -> ')}`)
  }
  if (tokens < 1) throw new Error('一个 token 都没收到')
  if (!text.trim()) throw new Error('拼出来的回答是空的')
  if (done.status !== 'completed') throw new Error(`status=${done.status}`)
  if (done.trace.length < 1) throw new Error('done 里没有 trace')
  if (!done.message_id || !done.conversation_id) throw new Error('done 缺 id')

  console.log('[smoke_sse] 全部通过 ✅')
}

main().catch((err) => {
  console.error(`[smoke_sse] 失败 ❌  ${err instanceof Error ? err.message : String(err)}`)
  process.exit(1)
})
