/** 泛型审核台(S0-PLAN Step 8)—— S1/S2/S3 的审核界面都是它的实例化。
 *
 * 它**不认识**待审内容是什么:payload 交给传进来的渲染器画,自己只负责这套流程 ——
 * 筛选 / 排序 / 单条通过驳回改 / 批量 / 键盘流 / 发布。所以加一类知识
 * (S2 的切片、S3 的指标)= 写两个渲染器,这个文件一行不改。
 *
 * ```tsx
 * <StagingReview jobId={id} itemRenderer={QaItemCard} editorRenderer={QaItemEditor} />
 * ```
 *
 * **两个刻意的设计决定**:
 *
 * 1. **默认按置信度升序**:最不靠谱的排最前。审核的时间应该花在最可能出错的地方,
 *    而不是从头翻到尾 —— 这也是抽取任务给每条打 confidence 的唯一用途。
 * 2. **选中项是推导出来的,不是一个状态**:`selectedId` 在当前列表里找不到就落到第一条。
 *    所以筛选变化、条目审完消失都不需要 effect 去同步选中态(effect 里同步 setState
 *    既会多一轮渲染,新版 react-hooks 规则也直接报错)。
 */

import { Check, Loader2, Send, Undo2, X } from 'lucide-react'
import { useEffect, useState, type ComponentType } from 'react'

import { apiPatch, apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import {
  confidenceTone,
  REVIEW_STATUSES,
  type PublishResult,
  type StagingItem,
  type StagingList,
  type StagingPatch,
  type StagingSummary,
} from '@/api/schema'
import { EmptyState } from '@/components/EmptyState'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

import type { ItemCardProps, ItemEditorProps, OriginPanelProps, Payload } from './staging/types'

const SORTS = [
  { value: 'confidence_asc', label: 'Least confident' },
  { value: 'confidence_desc', label: 'Most confident' },
  { value: 'created_asc', label: 'Extraction order' },
] as const

type Props = {
  jobId: string
  /** job 的状态决定发布按钮开不开(published 之后审核台变只读) */
  jobStatus?: string
  itemRenderer: ComponentType<ItemCardProps>
  editorRenderer: ComponentType<ItemEditorProps>
  originPanel?: ComponentType<OriginPanelProps>
  onPublished?: () => void
}

export function StagingReview({
  jobId,
  jobStatus,
  itemRenderer: Card,
  editorRenderer: Editor,
  originPanel: Origin,
  onPublished,
}: Props) {
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sort, setSort] = useState<string>('confidence_asc')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [draft, setDraft] = useState<{ id: string; payload: Payload } | null>(null)
  const [busy, setBusy] = useState(false)
  // 发布成功的那一刻就把界面切成只读:等 job 状态那一次往返(约一个轮询)期间,
  // 界面不该还允许"通过" —— 那一条通过了也永远发不出去(后端也会 409 拦住)
  const [justPublished, setJustPublished] = useState(false)

  const filter = statusFilter === 'all' ? '' : `&review_status=${statusFilter}`
  const list = useApi<StagingList>(`/api/staging?job_id=${jobId}&sort=${sort}${filter}`)
  const summary = useApi<StagingSummary>(`/api/staging/summary?job_id=${jobId}`)

  const items = list.data?.items ?? []
  const selected = items.find((i) => i.id === selectedId) ?? items[0] ?? null
  const dirty = draft !== null && selected !== null && draft.id === selected.id
  const payload = (dirty ? draft.payload : (selected?.payload ?? {})) as Payload
  const readOnly = jobStatus !== 'review' || justPublished || (selected?.published ?? false)

  const counts = summary.data
  const publishable = counts ? counts.approved + counts.modified : 0
  const canPublish = jobStatus === 'review' && publishable > 0

  // ---------------------------------------------------------------- 动作

  const nextAfter = (id: string): string | null => {
    const i = items.findIndex((it) => it.id === id)
    return items[i + 1]?.id ?? items[i - 1]?.id ?? null
  }

  const refresh = () => {
    list.reload()
    summary.reload()
  }

  const patchOne = async (item: StagingItem, body: StagingPatch, advance: boolean) => {
    setBusy(true)
    const next = advance ? nextAfter(item.id) : null
    try {
      await apiPatch<StagingItem>(`/api/staging/${item.id}`, body)
      setDraft(null)
      if (advance) setSelectedId(next)
      refresh()
    } catch {
      pushToast('error', 'review_failed', 'Could not save this item.')
    } finally {
      setBusy(false)
    }
  }

  // 通过时带上未保存的改动:审到一半改了内容再点通过,不该丢掉改动
  const approve = (item: StagingItem) =>
    void patchOne(
      item,
      { review_status: 'approved', payload: dirty && draft.id === item.id ? draft.payload : null },
      true,
    )
  const reject = (item: StagingItem) =>
    void patchOne(item, { review_status: 'rejected', payload: null }, true)
  const save = (item: StagingItem) =>
    void patchOne(item, { payload: dirty ? draft.payload : null }, false)

  const bulk = async (review_status: string) => {
    const ids = [...checked]
    if (!ids.length) return
    setBusy(true)
    try {
      const res = await apiPost<{ updated: number }>('/api/staging/bulk', { ids, review_status })
      setChecked(new Set())
      refresh()
      pushToast('success', `${res.updated} items ${review_status}`, '')
    } catch {
      pushToast('error', 'bulk_failed', 'Could not apply the bulk action.')
    } finally {
      setBusy(false)
    }
  }

  const publish = async () => {
    setBusy(true)
    try {
      const res = await apiPost<PublishResult>(`/api/jobs/${jobId}/publish`)
      setJustPublished(true)
      pushToast('success', `Published ${res.published} items`, 'A publish record was written.')
      refresh()
      onPublished?.()
    } catch {
      // 后端会以 409 拒绝重复发布 / 无可发布内容,message 已由 apiFetch 翻译
      pushToast('error', 'publish_failed', 'Nothing was published.')
    } finally {
      setBusy(false)
    }
  }

  const toggleCheck = (id: string) =>
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  // ---------------------------------------------------------------- 键盘流
  // 审几十条时快捷键把效率拉开:j/k 走条目、a 通过、x 驳回、空格勾选。
  // 输入框里按 a 当然是打字,所以先看事件目标是不是可编辑元素。
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return
      if (!selected || busy) return
      const move = (delta: number) => {
        const i = items.findIndex((it) => it.id === selected.id)
        const to = items[i + delta]
        if (to) {
          setSelectedId(to.id)
          setDraft(null)
        }
      }
      if (e.key === 'j') move(1)
      else if (e.key === 'k') move(-1)
      else if (e.key === 'a' && !readOnly) approve(selected)
      else if (e.key === 'x' && !readOnly) reject(selected)
      else if (e.key === ' ') {
        e.preventDefault()
        toggleCheck(selected.id)
      } else return
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // approve/reject 每次渲染都是新函数,但它们只读上面这些值 —— 依赖列到这些值就够
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, selected, busy, readOnly, dirty])

  // ---------------------------------------------------------------- 渲染

  if (list.loading && !list.data) return <Skeleton className="h-64 w-full" />

  return (
    <div className="flex h-[calc(100vh-9.5rem)] flex-col gap-4">
      {/* 筛选条:标签上的计数来自 summary 接口,不在前端数(前端只有当前页) */}
      {/* 筛选条:左边标签(挤了就换行),右边排序 + 发布固定不动 —— 发布是页面级动作,
          位置必须稳定,不能因为标签换行而跳到别处 */}
      <div className="bg-card flex items-start justify-between gap-3 rounded-[var(--radius-card)] border px-4 py-3 shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-center gap-1">
          <Tab
            label="All"
            count={counts?.total}
            active={statusFilter === 'all'}
            onClick={() => setStatusFilter('all')}
          />
          {REVIEW_STATUSES.map((s) => (
            <Tab
              key={s}
              label={s}
              count={counts?.[s]}
              active={statusFilter === s}
              onClick={() => setStatusFilter(s)}
            />
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="bg-card focus:border-primary h-9 rounded-[var(--radius)] border px-2 text-[13px] outline-none"
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          {/* 强调 CTA 一屏只有一个(UI-STYLE §3):发布 */}
          <Button variant="accent" disabled={!canPublish || busy} onClick={() => void publish()}>
            <Send />
            {jobStatus === 'published' ? 'Published' : `Publish ${publishable} approved`}
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-4">
        {/* 左:紧凑列表(48px 行高,UI-STYLE §3) */}
        <div className="bg-card flex w-[380px] shrink-0 flex-col overflow-hidden rounded-[var(--radius-card)] border shadow-[var(--shadow-card)]">
          <div className="text-muted-foreground flex items-center gap-2 border-b px-4 py-2 font-mono text-[11px] whitespace-nowrap">
            <span>{items.length} items</span>
            <span className="ml-auto">j / k · a approve · x reject · space select</span>
          </div>
          {items.length === 0 ? (
            <EmptyState
              icon={Check}
              title="Nothing here"
              description="No items match this filter."
            />
          ) : (
            <ul className="min-h-0 flex-1 overflow-y-auto">
              {items.map((item) => (
                <li key={item.id}>
                  <div
                    onClick={() => {
                      setSelectedId(item.id)
                      setDraft(null)
                    }}
                    className={cn(
                      'flex h-12 cursor-pointer items-center gap-3 border-b px-3 transition-colors',
                      selected?.id === item.id
                        ? 'bg-primary-soft border-l-primary border-l-[3px] pl-[9px]'
                        : 'hover:bg-subtle',
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked.has(item.id)}
                      onChange={() => toggleCheck(item.id)}
                      onClick={(e) => e.stopPropagation()}
                      className="accent-primary size-3.5 shrink-0"
                      aria-label="Select item"
                    />
                    <div className="min-w-0 flex-1">
                      <Card item={item} />
                    </div>
                    <ConfidenceBadge value={item.confidence} />
                    <ReviewDot status={item.review_status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
          {/* 批量操作栏吸底:勾了才出现,没勾时不占位置 */}
          {checked.size > 0 && (
            <div className="bg-primary-soft flex flex-wrap items-center gap-1.5 border-t px-3 py-2">
              <span className="text-primary text-[12px] font-medium">{checked.size} selected</span>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => void bulk('approved')}
              >
                <Check /> Approve
              </Button>
              <Button
                size="sm"
                variant="danger"
                disabled={busy}
                onClick={() => void bulk('rejected')}
              >
                <X /> Reject
              </Button>
              <button
                className="text-muted-foreground hover:text-foreground ml-auto px-1 text-[12px]"
                onClick={() => setChecked(new Set())}
                aria-label="Clear selection"
              >
                Clear
              </button>
            </div>
          )}
        </div>

        {/* 右:编辑区 */}
        <div className="bg-card flex min-w-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-card)] border shadow-[var(--shadow-card)]">
          {selected === null ? (
            <EmptyState
              icon={Check}
              title="Nothing to review"
              description="This job has no staged items."
            />
          ) : (
            <>
              <div className="flex items-center gap-2 border-b px-5 py-3">
                <span className="font-mono text-[12px]">{selected.item_type}</span>
                <StatusBadge status={selected.review_status} />
                <ConfidenceBadge value={selected.confidence} />
                {selected.published && <Badge tone="navy">published</Badge>}
                {dirty && <Badge tone="info">unsaved</Badge>}
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-5">
                <Editor
                  payload={payload}
                  disabled={readOnly || busy}
                  onChange={(patch) =>
                    setDraft({ id: selected.id, payload: { ...payload, ...patch } })
                  }
                />
                {Origin && (
                  <div className="mt-6 border-t pt-4">
                    <div className="text-muted-foreground mb-2 font-mono text-[11px] tracking-wide uppercase">
                      Source
                    </div>
                    <Origin item={selected} />
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 border-t px-5 py-3">
                <Button disabled={readOnly || busy} onClick={() => approve(selected)}>
                  {busy ? <Loader2 className="animate-spin" /> : <Check />}
                  Approve
                </Button>
                <Button
                  variant="danger"
                  disabled={readOnly || busy}
                  onClick={() => reject(selected)}
                >
                  <X /> Reject
                </Button>
                <Button
                  variant="secondary"
                  disabled={readOnly || busy || !dirty}
                  onClick={() => save(selected)}
                >
                  Save changes
                </Button>
                {dirty && (
                  <Button variant="ghost" size="sm" onClick={() => setDraft(null)}>
                    <Undo2 /> Discard
                  </Button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function Tab({
  label,
  count,
  active,
  onClick,
}: {
  label: string
  count?: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 rounded-[var(--radius)] px-3 py-1.5 text-[13px] transition-colors',
        active ? 'bg-primary text-primary-foreground' : 'text-secondary-foreground hover:bg-subtle',
      )}
    >
      <span className="capitalize">{label}</span>
      {count != null && (
        <span className={cn('font-mono text-[11px]', !active && 'text-muted-foreground')}>
          {count}
        </span>
      )}
    </button>
  )
}

function ConfidenceBadge({ value }: { value?: number | null }) {
  if (value == null) return null
  return (
    <Badge tone={confidenceTone(value)} className="shrink-0 font-mono">
      {value.toFixed(2)}
    </Badge>
  )
}

/** 列表里状态只用一个点(48px 行放不下徽标),颜色与 StatusBadge 同一套语义。 */
function ReviewDot({ status }: { status: string }) {
  const tone =
    status === 'approved'
      ? 'bg-success'
      : status === 'rejected'
        ? 'bg-destructive'
        : status === 'modified'
          ? 'bg-info'
          : 'bg-border'
  return <span className={cn('size-2 shrink-0 rounded-full', tone)} title={status} />
}
