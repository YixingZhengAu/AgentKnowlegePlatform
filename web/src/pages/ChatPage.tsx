/** 对话页(S0-PLAN Step 7.1)—— S0 的 DoD 主体:发一句话、流式回复、右侧看轨迹、DB 可查。
 *
 * 三块拼起来:会话列表(建/切/删)+ 消息流(`useChat` 消费 SSE)+ 右侧轨迹面板。
 *
 * **"新对话"没有对应的接口**:后端不传 conversation_id 就等于新开一轮,
 * 所以点 New chat 只是把本地状态清空 —— 少一次往返,也不会留下"建了但没发消息"的空会话。
 */

import { MessagesSquare, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { apiDelete } from '@/api/client'
import { useApi } from '@/api/hooks'
import type { AgentList, ConversationList } from '@/api/schema'
import { useChat, type ChatTurn } from '@/api/useChat'
import { ChatMessages } from '@/components/ChatMessages'
import { Composer } from '@/components/Composer'
import { EmptyState } from '@/components/EmptyState'
import { TracePanel } from '@/components/TracePanel'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useRightPanel } from '@/layouts/rightPanel'
import { fmtDateTime } from '@/lib/format'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

export function ChatPage() {
  const agents = useApi<AgentList>('/api/agents')
  const conversations = useApi<ConversationList>('/api/conversations')
  const agentId = agents.data?.items[0]?.id ?? null

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const chat = useChat(agentId, { onConversationCreated: () => conversations.reload() })

  // 右侧面板默认盯住最后一条助手消息;点某条气泡就切到那条(历史消息会去查完整 trace)
  const lastAssistant = [...chat.turns].reverse().find((t) => t.role === 'assistant')
  const selected =
    chat.turns.find((t) => t.id === selectedId && t.role === 'assistant') ?? lastAssistant

  useRightPanel(
    'Execution trace',
    <TracePanel
      spans={selected?.trace}
      messageId={selected?.id}
      streaming={chat.streaming}
      currentStage={chat.currentStage}
    />,
    [selected?.id, selected?.trace?.length, chat.streaming, chat.currentStage],
  )

  const openTurn = (turn: ChatTurn) => setSelectedId(turn.id)

  const remove = async (id: string) => {
    try {
      await apiDelete(`/api/conversations/${id}`)
      if (chat.conversationId === id) chat.newChat()
      conversations.reload()
    } catch {
      pushToast('error', 'delete_failed', 'Could not delete this conversation.')
    }
  }

  return (
    <div className="flex h-full min-h-0 gap-5">
      {/* 会话列表 */}
      <Card className="flex w-[240px] shrink-0 flex-col overflow-hidden">
        <div className="border-b border-[var(--border-soft)] p-3">
          <Button
            variant="secondary"
            size="sm"
            className="w-full"
            onClick={() => {
              chat.newChat()
              setSelectedId(null)
            }}
          >
            <Plus />
            New chat
          </Button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto p-2">
          {conversations.data?.items.map((c) => (
            <div
              key={c.id}
              className={cn(
                'group flex items-center gap-2 rounded-[var(--radius-row)] border px-3 py-2.5 transition-all duration-150',
                chat.conversationId === c.id
                  ? 'bg-selected border-[var(--selected-border)]'
                  : 'hover:bg-subtle border-transparent',
              )}
            >
              <button
                type="button"
                onClick={() => {
                  setSelectedId(null)
                  void chat.openConversation(c.id)
                }}
                className="min-w-0 flex-1 text-left"
              >
                <div
                  className={cn(
                    'truncate text-[13px] font-medium',
                    chat.conversationId === c.id && 'text-primary font-semibold',
                  )}
                >
                  {c.title ?? 'Untitled'}
                </div>
                <div className="text-fainter mt-px font-mono text-[10.5px]">
                  {fmtDateTime(c.last_message_at)}
                </div>
              </button>
              <button
                type="button"
                aria-label="Delete conversation"
                onClick={() => void remove(c.id)}
                className="text-ghost hover:text-destructive shrink-0 opacity-0 transition-opacity duration-150 group-hover:opacity-100"
              >
                <Trash2 className="size-3.5" strokeWidth={1.75} />
              </button>
            </div>
          ))}
          {conversations.data?.items.length === 0 && (
            <p className="text-faint p-4 text-[12.5px]">
              No conversations yet. Ask something on the right.
            </p>
          )}
        </div>
      </Card>

      {/* 消息流 + 输入框 */}
      <Card className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="min-h-0 flex-1 overflow-y-auto">
          {chat.turns.length === 0 ? (
            <EmptyState
              icon={MessagesSquare}
              title={agentId ? 'Ask the agent anything' : 'No agent configured'}
              description={
                agentId
                  ? 'The answer streams in token by token, and every stage it went through is recorded on the right.'
                  : 'Run `make seed` to create the default agent.'
              }
            />
          ) : (
            <ChatMessages
              turns={chat.turns}
              selectedId={selected?.id ?? null}
              onSelect={openTurn}
            />
          )}
        </div>
        <Composer
          // 流结束后再刷一次会话列表:标题与 last_message_at 是后端在这轮里写的
          onSend={(text) => void chat.send(text).then(() => conversations.reload())}
          onStop={chat.stop}
          streaming={chat.streaming}
          disabled={!agentId}
        />
      </Card>
    </div>
  )
}
