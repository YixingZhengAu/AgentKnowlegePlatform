/** 执行轨迹面板 v0(S0-PLAN Step 7.1)—— 这是整个演示的"可解释性"卖点。
 *
 * 数据有两个来源,刻意都支持:
 *
 * | 场景 | 来源 | 有什么 |
 * | --- | --- | --- |
 * | 正在流 / 刚答完 | SSE 的 `stage_end` 事件 | 阶段、耗时、token、成本 |
 * | 点开历史消息 | `GET /api/traces/{message_id}` | 上面全部 + input/output 全文摘要 |
 *
 * 所以历史消息能展开看"当时到底把什么 prompt 发出去了" —— 演示时最有说服力的一屏。
 * S1 的检索阶段、S4 的路由阶段会自动出现在这里,这个组件不用改。
 */

import { ChevronDown, ChevronRight, Route } from 'lucide-react'
import { useState } from 'react'

import { useApi } from '@/api/hooks'
import type { Trace, TraceList, TraceSpan } from '@/api/schema'
import { EmptyState } from '@/components/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtMs, fmtTokens, fmtUsd } from '@/lib/format'
import { cn } from '@/lib/utils'

/** 两种来源归一成同一行的形状,渲染只写一遍。 */
type TraceRow = {
  stage: string
  seq: number
  status: string
  latency_ms?: number | null
  model?: string | null
  tokens: string
  cost?: string | null
  error?: string | null
  input?: unknown
  output?: unknown
}

function fromSpan(s: TraceSpan): TraceRow {
  return {
    stage: s.stage,
    seq: s.seq,
    status: s.status,
    latency_ms: s.latency_ms,
    model: s.model,
    tokens: fmtTokens(s.usage),
    cost: s.cost_usd,
    error: s.error,
  }
}

function fromTrace(t: Trace): TraceRow {
  return {
    stage: t.stage,
    seq: t.seq,
    status: t.status,
    latency_ms: t.latency_ms,
    model: t.model,
    tokens:
      t.prompt_tokens == null && t.completion_tokens == null
        ? '—'
        : `${t.prompt_tokens ?? 0} + ${t.completion_tokens ?? 0}`,
    cost: t.cost_usd == null ? null : String(t.cost_usd),
    error: t.error,
    input: t.input,
    output: t.output,
  }
}

export function TracePanel({
  spans,
  messageId,
  streaming = false,
  currentStage = null,
}: {
  spans?: TraceSpan[] | null
  messageId?: string | null
  streaming?: boolean
  currentStage?: string | null
}) {
  // 流还在跑的时候不查接口:trace 要等助手消息落库之后才存在(见 core/chat.py)
  const wantFull = !streaming && !!messageId && !messageId.startsWith('local-')
  const full = useApi<TraceList>(wantFull ? `/api/traces/${messageId}` : null, {
    toastOnError: false,
  })

  const rows: TraceRow[] =
    full.data && full.data.items.length > 0
      ? full.data.items.map(fromTrace)
      : (spans ?? []).map(fromSpan)

  // 流刚开始、还没有任何 stage_end:能报出当前阶段就报,不然给个骨架
  if (rows.length === 0 && streaming) {
    return currentStage ? (
      <LiveStage stage={currentStage} />
    ) : (
      <div className="flex flex-col gap-2 p-[26px]">
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }
  if (rows.length === 0) {
    return (
      <EmptyState
        icon={Route}
        title="No trace yet"
        description="Every answer records its stages here: retrieval, routing and generation, each with latency, tokens and cost."
      />
    )
  }

  const totalMs = rows.reduce((sum, r) => sum + (r.latency_ms ?? 0), 0)

  return (
    <div className="flex flex-col px-[26px] pt-1 pb-[26px]">
      {rows.map((row, i) => (
        // key 里带 messageId:切到另一条消息时展开状态不该被复用(阶段名和 seq 是会重复的)
        <StageRow
          key={`${messageId ?? 'live'}-${row.seq}-${row.stage}`}
          row={row}
          last={i === rows.length - 1 && !(streaming && currentStage)}
        />
      ))}
      {streaming && currentStage && <LiveStage stage={currentStage} />}
      <div className="text-faint mt-2 flex justify-between rounded-[var(--radius-panel)] border border-[var(--border)] px-4 py-3 text-[12.5px]">
        <span>
          {rows.length} stage{rows.length > 1 ? 's' : ''}
        </span>
        <span className="font-mono">{fmtMs(totalMs)}</span>
      </div>
    </div>
  )
}

/** 正在跑的阶段:蓝点脉冲 + 阶段名(与已完成的阶段同一条时间轴) */
function LiveStage({ stage }: { stage: string }) {
  return (
    <div className="flex gap-3.5">
      <span className="bg-info-soft flex size-[22px] shrink-0 items-center justify-center rounded-full">
        <span className="bg-info size-1.5 animate-pulse rounded-full" />
      </span>
      <span className="text-faint pt-[3px] text-[13px] font-semibold">{stage}…</span>
    </div>
  )
}

/** 时间轴状态点:与 JobProgress 同一套(UI-STYLE §4),这里状态只有成功/失败两种。 */
const DOT: Record<string, string> = {
  ok: 'bg-success-dot',
  error: 'bg-destructive',
}

function StageRow({ row, last }: { row: TraceRow; last: boolean }) {
  const [open, setOpen] = useState(false)
  const expandable = row.input != null || row.output != null || row.error != null

  return (
    <div className="flex gap-3.5">
      <div className="flex shrink-0 flex-col items-center">
        <span
          className={cn(
            'flex size-[22px] shrink-0 items-center justify-center rounded-full',
            row.status === 'error' ? 'bg-destructive-soft' : 'bg-success-soft',
          )}
        >
          <span className={cn('size-1.5 rounded-full', DOT[row.status] ?? 'bg-fainter')} />
        </span>
        {!last && <span className="my-1 w-[1.5px] flex-1 bg-[var(--success-line)]" />}
      </div>
      <div className={cn('min-w-0 flex-1', !last && 'pb-[18px]')}>
      <button
        type="button"
        disabled={!expandable}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex w-full items-center gap-1.5 rounded-[var(--radius-nav)] py-px text-left',
          expandable && 'hover:text-primary',
        )}
      >
        <span className="text-[13px] font-semibold">{row.stage}</span>
        {expandable &&
          (open ? (
            <ChevronDown className="text-ghost size-3" />
          ) : (
            <ChevronRight className="text-ghost size-3" />
          ))}
        <span className="text-fainter ml-auto shrink-0 pl-2 text-right font-mono text-[10.5px]">
          {fmtMs(row.latency_ms)} · {row.tokens}
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-3 pt-2.5">
          <Meta label="model" value={row.model ?? '—'} />
          <Meta label="cost" value={fmtUsd(row.cost)} />
          {row.error && (
            <div>
              <div className="text-destructive mb-1 font-mono text-[10.5px] tracking-[0.06em] uppercase">
                error
              </div>
              <pre className="bg-destructive/5 text-destructive overflow-x-auto rounded-[var(--radius)] p-3 font-mono text-[11px] whitespace-pre-wrap">
                {row.error}
              </pre>
            </div>
          )}
          {row.input != null && <Json label="input" value={row.input} />}
          {row.output != null && <Json label="output" value={row.output} />}
        </div>
      )}
      </div>
    </div>
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between font-mono text-[11px]">
      <span className="text-fainter tracking-[0.06em] uppercase">{label}</span>
      <span>{value}</span>
    </div>
  )
}

function Json({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <div className="text-fainter mb-1 font-mono text-[10.5px] tracking-[0.06em] uppercase">
        {label}
      </div>
      <pre className="bg-muted max-h-64 overflow-auto rounded-[var(--radius)] p-3 font-mono text-[11px] whitespace-pre-wrap">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}
