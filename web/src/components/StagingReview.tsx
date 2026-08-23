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
 * 3. **动作是传进来的(S1-plan Step 7a)**:流程归本组件,"通过/驳回到底做了什么"归各域。
 *    S1 是采纳即发布(写正式表 + 建向量,没有批量发布),它只换 `actions`,本文件不认识它。
 *    不传 `actions` 就是 S0 的默认语义(标 approved,最后批量发布)。
 */

import { Check, Loader2, Send, Undo2, X } from 'lucide-react'
import { useEffect, useRef, useState, type ComponentType } from 'react'

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
import { Input } from '@/components/ui/input'
import { Kbd } from '@/components/ui/kbd'
import { Segmented, SegmentedItem } from '@/components/ui/segmented'
import { Skeleton } from '@/components/ui/skeleton'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

import type {
  ItemCardProps,
  ItemEditorProps,
  OriginPanelProps,
  Payload,
  ReviewActions,
} from './staging/types'

/** S0 的默认动作语义:标状态,最后由 job 批量发布。 */
const DEFAULT_ACTIONS: ReviewActions = {
  approveLabel: 'Approve',
  publish: true,
  bulk: true,
  approve: (item, payload) =>
    apiPatch<StagingItem>(`/api/staging/${item.id}`, { review_status: 'approved', payload }),
  reject: (item) =>
    apiPatch<StagingItem>(`/api/staging/${item.id}`, {
      review_status: 'rejected',
      payload: null,
    }),
}

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
  /** 本类知识的动作层;不给走 S0 默认(见 DEFAULT_ACTIONS) */
  actions?: ReviewActions
  /** 一条被裁决之后回调(S1 用它刷新正式 QA 列表 —— 采纳即发布,那边立刻多一行) */
  onDecided?: () => void
  onPublished?: () => void
}

export function StagingReview({
  jobId,
  jobStatus,
  itemRenderer: Card,
  editorRenderer: Editor,
  originPanel: Origin,
  actions: actionsProp,
  onDecided,
  onPublished,
}: Props) {
  const actions = actionsProp ?? DEFAULT_ACTIONS
  const [statusFilter, setStatusFilter] = useState<string>(actions.defaultStatusFilter ?? 'all')
  const [sort, setSort] = useState<string>('confidence_asc')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [draft, setDraft] = useState<{ id: string; payload: Payload } | null>(null)
  const [busy, setBusy] = useState(false)
  // 驳回理由:必填时点 Reject 先展开输入框,填了才真的提交(S1 的"不采纳"必须留痕)
  const [rejectNote, setRejectNote] = useState<string | null>(null)
  const noteRef = useRef<HTMLInputElement>(null)
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

  /** 一次裁决 = 跑动作 + 清草稿 + 可选前进 + 刷新。动作本身由 actions 决定(见文件头 3)。 */
  const runAction = async (item: StagingItem, fn: () => Promise<unknown>, advance: boolean) => {
    setBusy(true)
    const next = advance ? nextAfter(item.id) : null
    try {
      await fn()
      setDraft(null)
      setRejectNote(null)
      if (advance) setSelectedId(next)
      refresh()
      onDecided?.()
    } catch {
      pushToast('error', 'review_failed', 'Could not save this item.')
    } finally {
      setBusy(false)
    }
  }

  // 通过时带上未保存的改动:审到一半改了内容再点通过,不该丢掉改动
  const approve = (item: StagingItem) =>
    void runAction(
      item,
      () => actions.approve(item, dirty && draft.id === item.id ? draft.payload : null),
      true,
    )

  /** 驳回:要理由时第一次点只展开输入框(rejectNote===null 表示还没进驳回态)。 */
  const reject = (item: StagingItem) => {
    if (actions.requireRejectNote && rejectNote === null) {
      setRejectNote('')
      // 展开就聚焦,键盘流(x)不用再摸鼠标
      setTimeout(() => noteRef.current?.focus(), 0)
      return
    }
    const note = rejectNote ?? ''
    if (actions.requireRejectNote && !note.trim()) return
    void runAction(item, () => actions.reject(item, note), true)
  }

  const save = (item: StagingItem) =>
    void runAction(
      item,
      () =>
        apiPatch<StagingItem>(`/api/staging/${item.id}`, {
          payload: dirty ? draft.payload : null,
        } satisfies StagingPatch),
      false,
    )

  const bulk = async (review_status: string) => {
    const ids = [...checked]
    if (!ids.length) return
    setBusy(true)
    try {
      // 本域给了 bulkApprove 就用它(S1 的采纳=发布,一条条走本域接口);
      // 没给就是 S0 语义:一次请求只改 review_status
      const useDomain = review_status === 'approved' && actions.bulkApprove
      const updated = useDomain
        ? await actions.bulkApprove!(items.filter((i) => checked.has(i.id)))
        : (await apiPost<{ updated: number }>('/api/staging/bulk', { ids, review_status })).updated
      setChecked(new Set())
      refresh()
      onDecided?.()
      const suffix = updated < ids.length ? ` (${ids.length - updated} failed)` : ''
      pushToast(
        updated < ids.length ? 'error' : 'success',
        `${updated} items ${review_status}${suffix}`,
        '',
      )
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
          setRejectNote(null)
        }
      }
      if (e.key === 'j') move(1)
      else if (e.key === 'k') move(-1)
      else if (e.key === 'a' && !readOnly) approve(selected)
      else if (e.key === 'x' && !readOnly) reject(selected)
      else if (e.key === ' ' && actions.bulk) {
        e.preventDefault()
        toggleCheck(selected.id)
      } else return
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // approve/reject 每次渲染都是新函数,但它们只读上面这些值 —— 依赖列到这些值就够
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, selected, busy, readOnly, dirty, rejectNote])

  // ---------------------------------------------------------------- 渲染

  if (list.loading && !list.data) return <Skeleton className="h-64 w-full" />

  return (
    <div className="flex h-[calc(100vh-10.5rem)] flex-col">
      {/* 筛选条:标签上的计数来自 summary 接口,不在前端数(前端只有当前页) */}
      {/* 筛选条:左边标签(挤了就换行),右边排序 + 发布固定不动 —— 发布是页面级动作,
          位置必须稳定,不能因为标签换行而跳到别处 */}
      <div className="mb-5 flex shrink-0 items-center justify-between gap-4">
        <Segmented className="flex-wrap">
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
        </Segmented>
        <div className="flex shrink-0 items-center gap-4">
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="hover:bg-subtle bg-card h-9 cursor-pointer rounded-[var(--radius-pill)] border border-[var(--border-strong)] px-[14px] text-[12.5px] font-medium transition-all duration-150 outline-none"
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          {/* 强调 CTA 一屏只有一个(UI-STYLE §3):发布。
              采纳即发布的域没有这一步 —— 不留一个永远点不动的按钮,改显示已入库条数 */}
          {actions.publish ? (
            <Button variant="accent" disabled={!canPublish || busy} onClick={() => void publish()}>
              <Send />
              {jobStatus === 'published' ? 'Published' : `Publish ${publishable} approved`}
            </Button>
          ) : (
            <span className="text-faint flex items-center gap-[7px] text-[12px] whitespace-nowrap">
              <span className="bg-success-dot size-[7px] rounded-full" />
              {publishable} accepted · live
            </span>
          )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-5">
        {/* 左:条目列表 —— 行是独立的圆角块,不是表格行(UI-STYLE §4) */}
        <div className="flex w-[376px] shrink-0 flex-col">
          <div className="text-fainter flex shrink-0 items-center gap-1.5 px-1 pb-2.5 text-[11px] tracking-[0.02em] whitespace-nowrap">
            <span className="text-faint font-medium">{items.length} items</span>
            <span className="ml-auto flex items-center gap-1.5 font-mono text-[10.5px]">
              <Kbd>j / k</Kbd>
              <Kbd>a</Kbd> approve <Kbd>x</Kbd> reject{actions.bulk ? ' · space select' : ''}
            </span>
          </div>
          {items.length === 0 ? (
            <EmptyState
              icon={Check}
              title="Nothing here"
              description="No items match this filter."
            />
          ) : (
            <ul className="-mx-1 flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto px-1 pt-0.5 pb-2">
              {items.map((item) => (
                <li key={item.id}>
                  <div
                    onClick={() => {
                      setSelectedId(item.id)
                      setDraft(null)
                      setRejectNote(null)
                    }}
                    className={cn(
                      'flex cursor-pointer items-start gap-3 rounded-[var(--radius-row)] border px-3.5 py-2.5 transition-all duration-150',
                      selected?.id === item.id
                        ? 'is-sel bg-selected border-[var(--selected-border)] shadow-[var(--shadow-row)]'
                        : 'hover:bg-subtle border-transparent',
                    )}
                  >
                    {actions.bulk && (
                      <input
                        type="checkbox"
                        checked={checked.has(item.id)}
                        onChange={() => toggleCheck(item.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="accent-primary mt-0.5 size-[15px] shrink-0 rounded-[5px]"
                        aria-label="Select item"
                      />
                    )}
                    <div className="min-w-0 flex-1">
                      <Card item={item} />
                    </div>
                    <ConfidenceBadge value={item.confidence} className="mt-px" />
                    <ReviewDot status={item.review_status} />
                  </div>
                </li>
              ))}
            </ul>
          )}
          {/* 批量操作栏吸底:勾了才出现,没勾时不占位置 */}
          {checked.size > 0 && (
            <div className="bg-selected mt-2 flex shrink-0 flex-wrap items-center gap-2 rounded-[var(--radius-row)] border border-[var(--selected-border)] px-3 py-2.5">
              <span className="text-primary text-[12px] font-semibold">{checked.size} selected</span>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => void bulk('approved')}
              >
                <Check /> Approve
              </Button>
              {actions.bulkReject !== false && (
                <Button
                  size="sm"
                  variant="danger"
                  disabled={busy}
                  onClick={() => void bulk('rejected')}
                >
                  <X /> Reject
                </Button>
              )}
              <button
                className="text-faint hover:text-foreground ml-auto px-1 text-[12px] transition-colors duration-150"
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
              <div className="flex h-[54px] shrink-0 items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
                <span className="font-mono text-[12px]">{selected.item_type}</span>
                <StatusBadge status={selected.review_status} />
                <ConfidenceBadge value={selected.confidence} className="ml-auto h-6 text-[12px]" />
                {selected.published && <Badge tone="navy">published</Badge>}
                {dirty && <Badge tone="info">unsaved</Badge>}
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto px-7 pt-[26px] pb-[30px] [&>*]:max-w-[680px]">
                <Editor
                  payload={payload}
                  disabled={readOnly || busy}
                  onChange={(patch) =>
                    setDraft({ id: selected.id, payload: { ...payload, ...patch } })
                  }
                />
                {Origin && (
                  <div className="mt-6 max-w-[680px] border-t border-[var(--border-soft)] pt-5">
                    <div className="mb-[7px] text-[12.5px] font-semibold">Source</div>
                    <Origin item={selected} />
                  </div>
                )}
              </div>

              <div className="flex shrink-0 flex-wrap items-center gap-2 border-t border-[var(--border-soft)] px-5 py-4">
                <Button disabled={readOnly || busy} onClick={() => approve(selected)}>
                  {busy ? <Loader2 className="animate-spin" /> : <Check />}
                  {actions.approveLabel}
                </Button>
                {/* 理由必填时,Reject 先展开输入框(第二次点才真提交) */}
                {rejectNote !== null && (
                  <Input
                    ref={noteRef}
                    value={rejectNote}
                    disabled={busy}
                    onChange={(e) => setRejectNote(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') reject(selected)
                      if (e.key === 'Escape') setRejectNote(null)
                    }}
                    placeholder="Why is this rejected? (required)"
                    className="w-[260px]"
                    aria-label="Rejection reason"
                  />
                )}
                <Button
                  variant="danger"
                  disabled={
                    readOnly || busy || (rejectNote !== null && rejectNote.trim() === '')
                  }
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
  return <SegmentedItem onClick={onClick} active={active} label={label} count={count} />
}

function ConfidenceBadge({ value, className }: { value?: number | null; className?: string }) {
  if (value == null) return null
  return (
    <Badge
      tone={confidenceTone(value)}
      className={cn('shrink-0 px-[9px] font-mono text-[11px] font-medium', className)}
    >
      {value.toFixed(2)}
    </Badge>
  )
}

/** 列表里状态只用一个点(行里放不下徽标),颜色与 StatusBadge 同一套语义。 */
function ReviewDot({ status }: { status: string }) {
  const tone =
    status === 'approved'
      ? 'bg-success'
      : status === 'rejected'
        ? 'bg-destructive'
        : status === 'modified'
          ? 'bg-info'
          : 'bg-border'
  return <span className={cn('mt-2 size-[7px] shrink-0 rounded-full', tone)} title={status} />
}
