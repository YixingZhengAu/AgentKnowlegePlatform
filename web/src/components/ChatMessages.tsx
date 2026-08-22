/** 消息流与气泡(UI-STYLE §3:用户 navy 底白字右对齐,助手白卡片左对齐)。
 *
 * 助手消息的元信息(耗时 / token / 状态)直接挂在气泡底下 ——
 * 演示时不需要点开右侧面板就能看到"这次花了多少"。
 *
 * **Verified Answer(S1)**:命中精准问答时,内容是人工采纳过的标准答案**原样返回**
 * (没过生成模型)。这件事必须在气泡上一眼看见 —— 它是"精准问答"这类知识存在的理由。
 * 标注用强调色(UI-STYLE §1:黄色 = 此刻该看这里),并把引用摆在正文下面。
 */

import { AlertTriangle, BadgeCheck } from 'lucide-react'
import { useEffect, useRef } from 'react'

import type { ChatTurn } from '@/api/useChat'
import { Citations } from '@/components/Citations'
import { Badge } from '@/components/ui/badge'
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
          /* 气泡本身可点(点它 = 右侧面板切到这条的 trace),但**不能是 <button>**:
             引用条里还有真按钮,button 套 button 是非法 HTML(React 会直接报错)——
             Step 7d 的浏览器自测就是被控制台这条 error 抓到的 */
          <div
            key={turn.id}
            role="button"
            tabIndex={0}
            onClick={() => onSelect(turn)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onSelect(turn)
              }
            }}
            className={cn(
              'bg-card max-w-[85%] rounded-[var(--radius-card)] border px-4 py-3 text-left shadow-[var(--shadow-card)] transition-colors',
              selectedId === turn.id && 'border-primary',
              // 命中的答案左侧一道强调色边:扫一眼消息流就知道哪几句是"库里的原话"
              turn.verified && 'border-l-accent border-l-[3px]',
            )}
          >
            {turn.verified && (
              <Badge tone="accent" className="mb-2 font-bold">
                <BadgeCheck className="size-3.5" />
                Verified Answer
              </Badge>
            )}
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
            {turn.citations && turn.citations.length > 0 && (
              <Citations items={turn.citations} />
            )}
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
          </div>
        ),
      )}
      <div ref={endRef} />
    </div>
  )
}
