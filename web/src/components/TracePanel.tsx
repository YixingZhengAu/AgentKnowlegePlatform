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
      <div className="flex flex-col gap-2 p-5">
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
    <div className="flex flex-col">
      {rows.map((row) => (
        // key 里带 messageId:切到另一条消息时展开状态不该被复用(阶段名和 seq 是会重复的)
        <StageRow key={`${messageId ?? 'live'}-${row.seq}-${row.stage}`} row={row} />
      ))}
      {streaming && currentStage && <LiveStage stage={currentStage} />}
      <div className="text-muted-foreground flex justify-between border-t px-5 py-3 text-[12px]">
        <span>
          {rows.length} stage{rows.length > 1 ? 's' : ''}
        </span>
        <span className="font-mono">{fmtMs(totalMs)}</span>
      </div>
    </div>
  )
}

/** 正在跑的阶段:蓝点脉冲 + 阶段名(与已完成的行同一套排版) */
function LiveStage({ stage }: { stage: string }) {
  return (
    <div className="text-muted-foreground flex items-center gap-2 border-b px-5 py-3 font-mono text-[12px] last:border-0">
      <span className="bg-info size-2 animate-pulse rounded-full" />
      {stage}…
    </div>
  )
}

const DOT: Record<string, string> = {
  ok: 'bg-success',
  error: 'bg-destructive',
}

function StageRow({ row }: { row: TraceRow }) {
  const [open, setOpen] = useState(false)
  const expandable = row.input != null || row.output != null || row.error != null

  return (
    <div className="border-b last:border-0">
      <button
        type="button"
        disabled={!expandable}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex w-full items-center gap-2 px-5 py-3 text-left',
          expandable && 'hover:bg-subtle',
        )}
      >
        <span className={cn('size-2 shrink-0 rounded-full', DOT[row.status] ?? 'bg-muted')} />
        <span className="font-mono text-[12px] font-medium">{row.stage}</span>
        {expandable &&
          (open ? (
            <ChevronDown className="text-muted-foreground size-3" />
          ) : (
            <ChevronRight className="text-muted-foreground size-3" />
          ))}
        <span className="text-muted-foreground ml-auto shrink-0 text-right font-mono text-[11px]">
          {fmtMs(row.latency_ms)} · {row.tokens}
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-3 px-5 pb-4">
          <Meta label="model" value={row.model ?? '—'} />
          <Meta label="cost" value={fmtUsd(row.cost)} />
          {row.error && (
            <div>
              <div className="text-destructive mb-1 font-mono text-[11px] uppercase">error</div>
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
  )
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between font-mono text-[11px]">
      <span className="text-muted-foreground uppercase">{label}</span>
      <span>{value}</span>
    </div>
  )
}

function Json({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <div className="text-muted-foreground mb-1 font-mono text-[11px] uppercase">{label}</div>
      <pre className="bg-muted max-h-64 overflow-auto rounded-[var(--radius)] p-3 font-mono text-[11px] whitespace-pre-wrap">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}
