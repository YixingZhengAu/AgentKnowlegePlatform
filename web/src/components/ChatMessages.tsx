/** 消息流与气泡(UI-STYLE §3:用户 navy 底白字右对齐,助手白卡片左对齐)。
 *
 * 助手消息的元信息(耗时 / token / 状态)直接挂在气泡底下 ——
 * 演示时不需要点开右侧面板就能看到"这次花了多少"。
 */

import { AlertTriangle } from 'lucide-react'
import { useEffect, useRef } from 'react'

import type { ChatTurn } from '@/api/useChat'
import { fmtMs, fmtTokens, fmtUsd } from '@/lib/format'
import { cn } from '@/lib/utils'

export function ChatMessages({
  turns,
  selectedId,
  onSelect,
}: {
  turns: ChatTurn[]
  selectedId: string | null
  onSelect: (turn: ChatTurn) => void
}) {
  const endRef = useRef<HTMLDivElement>(null)

  // 每来一个 token 就跟到底部。依赖里放的是总字符数,所以流式期间每帧都会滚。
  const chars = turns.reduce((n, t) => n + t.content.length, 0)
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [chars, turns.length])

  return (
    /* justify-end + min-h-full:消息少的时候贴着输入框,不在大片空白顶上飘着 */
    <div className="flex min-h-full flex-col justify-end gap-4 px-6 py-5">
      {turns.map((turn) =>
        turn.role === 'user' ? (
          <div key={turn.id} className="flex justify-end">
            <div className="bg-primary text-primary-foreground max-w-[75%] rounded-[var(--radius-card)] px-4 py-2.5 text-[14px] whitespace-pre-wrap">
              {turn.content}
            </div>
          </div>
        ) : (
          <button
            key={turn.id}
            type="button"
            onClick={() => onSelect(turn)}
            className={cn(
              'bg-card max-w-[85%] rounded-[var(--radius-card)] border px-4 py-3 text-left shadow-[var(--shadow-card)] transition-colors',
              selectedId === turn.id && 'border-primary',
            )}
          >
            <div className="text-[14px] whitespace-pre-wrap">
              {/* 气泡为空的两种情况都要说明白:还在等第一个 token / 第一个 token 之前就停了 */}
              {turn.content === '' ? (
                <span className="text-muted-foreground font-mono text-[12px]">
                  {turn.status === 'streaming'
                    ? 'thinking…'
                    : 'Stopped before the first token arrived.'}
                </span>
              ) : (
                turn.content
              )}
              {turn.content !== '' && turn.status === 'streaming' && (
                <span className="bg-primary ml-0.5 inline-block h-3.5 w-[2px] animate-pulse align-middle" />
              )}
            </div>
            {turn.error && (
              <div className="text-destructive mt-2 flex items-start gap-1.5 font-mono text-[11px]">
                <AlertTriangle className="mt-0.5 size-3 shrink-0" />
                {turn.error}
              </div>
            )}
            {/* 计量只显示真有值的那几项:中断的消息没有 usage,不该摆一排破折号 */}
            {turn.status !== 'streaming' && (
              <div className="text-muted-foreground mt-2 flex flex-wrap gap-3 font-mono text-[11px]">
                {turn.latency_ms != null && <span>{fmtMs(turn.latency_ms)}</span>}
                {turn.usage?.total_tokens ? <span>{fmtTokens(turn.usage)} tok</span> : null}
                {turn.usage?.cost_usd ? <span>{fmtUsd(turn.usage.cost_usd as string)}</span> : null}
                {turn.status !== 'completed' && <span>{turn.status}</span>}
              </div>
            )}
          </button>
        ),
      )}
      <div ref={endRef} />
    </div>
  )
}
