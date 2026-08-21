/** 对话页 —— Step 6 只立形状:布局位置 + 右侧轨迹面板插槽。
 *
 * 真正的输入框、消息流与流式渲染是 Step 7 的活;
 * 它要用的两块地基已经就位:`api/sse.ts`(事件协议客户端)与这里的右侧面板插槽。
 */

import { MessagesSquare, Route } from 'lucide-react'

import { useApi } from '@/api/hooks'
import type { ConversationList } from '@/api/schema'
import { EmptyState } from '@/components/EmptyState'
import { StatusBadge } from '@/components/StatusBadge'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { useRightPanel } from '@/layouts/AppLayout'
import { fmtDateTime } from '@/lib/format'

export function ChatPage() {
  const state = useApi<ConversationList>('/api/conversations')

  // 右侧面板的位置现在就占住:Step 7 把这里换成真实的 stage 列表
  useRightPanel(
    'Execution trace',
    <EmptyState
      icon={Route}
      title="No trace yet"
      description="Every answer records its stages here: retrieval, routing and generation, each with latency, tokens and cost."
    />,
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Conversations</CardTitle>
        <CardDescription>
          Ask a question and the agent decides which knowledge tier answers it. Every step of that
          decision is recorded and shown on the right.
        </CardDescription>
      </CardHeader>
      {state.data && state.data.items.length > 0 ? (
        <Table>
          <THead>
            <TR>
              <TH>Title</TH>
              <TH>Status</TH>
              <TH>Last message</TH>
            </TR>
          </THead>
          <tbody>
            {state.data.items.map((c) => (
              <TR key={c.id}>
                <TD className="font-medium">{c.title ?? 'Untitled'}</TD>
                <TD>
                  <StatusBadge status={c.status} />
                </TD>
                <TD className="text-muted-foreground text-[12px]">
                  {fmtDateTime(c.last_message_at)}
                </TD>
              </TR>
            ))}
          </tbody>
        </Table>
      ) : (
        <EmptyState
          icon={MessagesSquare}
          title="No conversations yet"
          description="The chat composer arrives with the conversation workspace."
        />
      )}
    </Card>
  )
}
