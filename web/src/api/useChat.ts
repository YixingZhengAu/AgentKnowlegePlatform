/** 对话状态机 —— Step 7 的核心前端逻辑。
 *
 * 为什么是一个 hook 而不是页面里的一堆 useState:流式回答期间有五件事在同时变
 * (助手消息内容、当前 stage、trace 列表、会话 id、错误),把它们放在一起才说得清。
 *
 * **两个关键决定**:
 *
 * 1. **历史消息是"点了才取",不用 effect 跟着 conversationId 自动取。**
 *    新开的会话是后端在流的第一个事件(`meta`)里才告诉前端 id 的;
 *    如果有个 effect 盯着 conversationId 自动拉历史,它会在流还没结束时把
 *    正在流的消息覆盖掉。所以取数只发生在用户点会话的那一刻(`openConversation`)。
 * 2. **助手消息的 id 用后端给的 `message_id`(meta 事件里)。**
 *    这样流完之后,右侧面板要查完整 trace(`GET /api/traces/{id}`)时不需要另找 id。
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, apiFetch } from './client'
import type { MessageList, TraceSpan } from './schema'
import { streamChat } from './sse'
import { pushToast } from '@/lib/toast'

export type ChatTurn = {
  /** 用户消息是本地临时 id;助手消息用后端 message_id(trace 查询要用) */
  id: string
  role: 'user' | 'assistant'
  content: string
  /** streaming | completed | failed | interrupted */
  status: string
  usage?: Record<string, unknown> | null
  latency_ms?: number | null
  /** 流式期间由 stage_end 事件累积;历史消息为空(要看就去查 traces 接口) */
  trace?: TraceSpan[]
  error?: string | null
}

export type ChatState = {
  conversationId: string | null
  turns: ChatTurn[]
  /** 正在流的助手消息(用于右侧面板实时显示 stage) */
  streaming: boolean
  currentStage: string | null
  send: (question: string) => Promise<void>
  stop: () => void
  newChat: () => void
  openConversation: (id: string) => Promise<void>
}

let localSeq = 0
const localId = () => `local-${++localSeq}`

export function useChat(
  agentId: string | null,
  opts?: { onConversationCreated?: (id: string) => void },
): ChatState {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [streaming, setStreaming] = useState(false)
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  // 回调放 ref:页面每次渲染都会给一个新函数,不该因此重建 send。
  // 赋值必须在 effect 里做 —— 渲染期间写 ref 是不允许的(react-hooks/refs)。
  const createdCb = useRef(opts?.onConversationCreated)
  const onCreated = opts?.onConversationCreated
  useEffect(() => {
    createdCb.current = onCreated
  }, [onCreated])

  const patchTurn = useCallback((id: string, patch: Partial<ChatTurn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)))
  }, [])

  const newChat = useCallback(() => {
    abortRef.current?.abort()
    setConversationId(null)
    setTurns([])
    setCurrentStage(null)
  }, [])

  const openConversation = useCallback(async (id: string) => {
    abortRef.current?.abort()
    setConversationId(id)
    setCurrentStage(null)
    try {
      const list = await apiFetch<MessageList>(`/api/conversations/${id}/messages`)
      setTurns(
        list.items.map((m) => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          status: m.status,
          usage: m.usage,
          latency_ms: m.latency_ms,
        })),
      )
    } catch (err) {
      const e = err as ApiError
      pushToast('error', e.code, e.message)
      setTurns([])
    }
  }, [])

  const send = useCallback(
    async (question: string) => {
      if (!agentId || streaming) return
      const text = question.trim()
      if (!text) return

      const userTurn: ChatTurn = { id: localId(), role: 'user', content: text, status: 'completed' }
      // 助手消息先占位:它的 id 在 meta 事件到达时被换成后端的 message_id
      const placeholderId = localId()
      setTurns((prev) => [
        ...prev,
        userTurn,
        { id: placeholderId, role: 'assistant', content: '', status: 'streaming', trace: [] },
      ])
      setStreaming(true)

      const ctrl = new AbortController()
      abortRef.current = ctrl
      let assistantId = placeholderId

      try {
        await streamChat({
          agentId,
          question: text,
          conversationId,
          signal: ctrl.signal,
          handlers: {
            onMeta: ({ message_id, conversation_id }) => {
              assistantId = message_id
              patchTurn(placeholderId, { id: message_id })
              if (!conversationId) {
                setConversationId(conversation_id)
                createdCb.current?.(conversation_id)
              }
            },
            onStageStart: ({ stage }) => setCurrentStage(stage),
            onToken: (chunk) =>
              setTurns((prev) =>
                prev.map((t) => (t.id === assistantId ? { ...t, content: t.content + chunk } : t)),
              ),
            onStageEnd: (span) =>
              setTurns((prev) =>
                prev.map((t) =>
                  t.id === assistantId ? { ...t, trace: [...(t.trace ?? []), span] } : t,
                ),
              ),
            // 流内错误:后端随后会用 token 事件发兜底话术,所以这里只记错误,不改内容
            onError: ({ message }) => patchTurn(assistantId, { error: message }),
            onDone: (done) =>
              patchTurn(assistantId, {
                status: done.status,
                // 成本在 done 里是独立字段,但落库时是塞进 usage 的(见 core/chat.py 的 _persist),
                // 这里跟着合并,历史消息与刚答完的消息才是同一种形状
                usage: { ...done.usage, cost_usd: done.cost_usd },
                latency_ms: done.latency_ms,
                trace: done.trace,
              }),
          },
        })
      } catch (err) {
        if (ctrl.signal.aborted) {
          // 用户自己点的 Stop:后端会把这条消息落成 interrupted,前端如实显示
          patchTurn(assistantId, { status: 'interrupted' })
        } else {
          const e = err as ApiError
          pushToast('error', e.code ?? 'stream_failed', e.message)
          patchTurn(assistantId, { status: 'failed', error: e.message })
        }
      } finally {
        abortRef.current = null
        setStreaming(false)
        setCurrentStage(null)
      }
    },
    [agentId, conversationId, streaming, patchTurn],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])

  return { conversationId, turns, streaming, currentStage, send, stop, newChat, openConversation }
}
