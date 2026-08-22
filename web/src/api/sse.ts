/** chat 接口的 SSE 客户端 —— 前端最需要先趟平的技术点(S0-PLAN Step 6.3)。
 *
 * 为什么不用 EventSource:EventSource 只能 GET、不能带 body。
 * 所以用 fetch + ReadableStream 自己解 SSE 帧。
 *
 * 事件协议出处:server/app/api/architect.md(改协议要前后端一起改)
 *   meta -> stage_start -> token* -> stage_end -> done
 * S1 起,命中精准问答时中间会多一个 `verified` 事件,且**没有 generate 阶段**
 * (答案原样返回,零改写)——协议只增不改,老逻辑照跑。
 * 三条后端给的保证,前端直接依赖:
 *   1. `done` 是唯一终止信号(哪怕编排根本没开始就失败,也会补一个 error + done)
 *   2. 失败时的兜底话术也走 `token`,所以渲染路径只有一条
 *   3. 一旦开始流,HTTP 状态码就定死 200 —— 所以流内的 `error` 事件才是错误来源
 */

// 这里的 `.ts` 后缀是故意的:scripts/smoke_sse.ts 用 Node 原生跑这份文件,
// Node 的 ESM 不做扩展名补全(Vite 两种写法都认)。
import { API_BASE, ApiError, toApiError } from './client.ts'
import type { ChatResponse, MessageCitation, TraceSpan } from './schema'

export type ChatStreamHandlers = {
  onMeta?: (data: { message_id: string; conversation_id: string }) => void
  onStageStart?: (data: { stage: string }) => void
  onToken?: (text: string) => void
  onStageEnd?: (span: TraceSpan) => void
  /** S1 新增:这次回答命中了人工采纳过的精准问答,内容是标准答案原样返回(没过生成模型) */
  onVerified?: (data: {
    score?: number | null
    matched_question?: string | null
    citations?: MessageCitation[]
  }) => void
  /** 流内错误:这次回答失败了,但连接是正常的(后面还会有 done) */
  onError?: (data: { stage?: string; message: string }) => void
  onDone?: (data: ChatResponse) => void
}

export type ChatStreamOptions = {
  agentId: string
  question: string
  conversationId?: string | null
  handlers: ChatStreamHandlers
  signal?: AbortSignal
}

/** 把一帧 SSE 文本(`event: x\ndata: {...}`)解成 [事件名, 负载]。 */
export function parseSseFrame(frame: string): { event: string; data: unknown } | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const rawLine of frame.split('\n')) {
    const line = rawLine.trimEnd()
    if (line.startsWith(':') || line === '') continue // 注释帧/心跳
    const idx = line.indexOf(':')
    const field = idx === -1 ? line : line.slice(0, idx)
    // 规范:字段名后的第一个空格要吃掉
    const value = idx === -1 ? '' : line.slice(idx + 1).replace(/^ /, '')
    if (field === 'event') event = value
    else if (field === 'data') dataLines.push(value)
  }
  if (dataLines.length === 0) return null
  const raw = dataLines.join('\n')
  try {
    return { event, data: JSON.parse(raw) }
  } catch {
    return { event, data: raw }
  }
}

/** 发起一次流式问答。resolve 的值是 `done` 事件的负载(与非流式返回体同形)。 */
export async function streamChat(opts: ChatStreamOptions): Promise<ChatResponse> {
  const { agentId, question, conversationId, handlers, signal } = opts

  const res = await fetch(`${API_BASE}/api/agents/${agentId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ question, conversation_id: conversationId ?? null, stream: true }),
    signal,
  }).catch((cause) => {
    if (signal?.aborted) throw cause
    throw new ApiError('network_error', 'Cannot reach the API server.', 0, String(cause))
  })

  // 流还没开始就失败的情况(参数校验 422、DB 不通 503):返回体是 JSON 而不是 SSE
  if (!res.ok || !res.body) throw await toApiError(res)

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  let done: ChatResponse | null = null

  try {
    for (;;) {
      const { value, done: finished } = await reader.read()
      if (finished) break
      buffer += value

      // SSE 帧以空行分隔;\r\n 也要认(经过代理时可能被改写)
      let sep: number
      while ((sep = buffer.search(/\r?\n\r?\n/)) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + buffer.slice(sep).match(/^\r?\n\r?\n/)![0].length)
        const parsed = parseSseFrame(frame)
        if (!parsed) continue
        dispatch(parsed.event, parsed.data, handlers)
        if (parsed.event === 'done') done = parsed.data as ChatResponse
      }
    }
  } finally {
    reader.cancel().catch(() => {})
  }

  // 没收到 done 就断了(后端进程挂了 / 网络断了):必须报错,不能假装成功
  if (!done) throw new ApiError('stream_incomplete', 'The answer stream ended unexpectedly.', 0)
  return done
}

function dispatch(event: string, data: unknown, h: ChatStreamHandlers) {
  switch (event) {
    case 'meta':
      h.onMeta?.(data as { message_id: string; conversation_id: string })
      break
    case 'stage_start':
      h.onStageStart?.(data as { stage: string })
      break
    case 'token':
      h.onToken?.((data as { text: string }).text)
      break
    case 'stage_end':
      h.onStageEnd?.(data as TraceSpan)
      break
    case 'verified':
      h.onVerified?.(data as { score?: number; matched_question?: string; citations?: MessageCitation[] })
      break
    case 'error':
      h.onError?.(data as { stage?: string; message: string })
      break
    case 'done':
      h.onDone?.(data as ChatResponse)
      break
    // 未知事件类型直接忽略:S1–S4 会加新事件,老前端不能因此崩
  }
}
