/** D3 意图列表页 —— 本域的 kb 级页面:**一个知识库里有哪些问题被做成了模板**。
 *
 * 四个设计决定:
 *
 * 1. **生成走 Job,采纳走通用审核台**。一批意图是十几次 gpt-5 调用,提交完必须能离开页面;
 *    候选的筛选/编辑/批量采纳对三类知识是同一套流程,所以这里只把人送到
 *    `/jobs/{id}/review`(渲染器与动作见 `renderers.tsx` / `actions.ts`),不自己造一个列表。
 * 2. **追加生成安全**:生成 prompt 会把已有意图的摘要喂回去要求避重
 *    (`ingest.py::step_generate` 的 `avoid`),已采纳的意图不受影响 —— 所以这一页上
 *    "再生成一批"是可以反复点的动作,不是"重置"。
 * 3. **状态是三档不是两档**:draft(采纳了但没验收)/ published(进检索了)/
 *    disabled(下线了,正式行还在)。列表默认全看 —— 这一页是知识资产台账,
 *    不是工作队列,人要能看见"有 4 条还是草稿"。
 * 4. **空路由负例面摆在这一页**。它是 **kb 级**资产(不属于任何单个意图),而本域里
 *    kb 级的页面就是这一页;Agent 设置页属于 shared 层,域开发者不该往里塞本域资产。
 *    它也不是可选调优项 —— 清空等于关掉空路由(见面板里那句话)。
 */

import {
  AlertTriangle,
  ArrowLeft,
  Check,
  ClipboardCheck,
  Database,
  ListTree,
  Loader2,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { apiDelete, apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
import { JobProgress } from '@/components/JobProgress'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Segmented, SegmentedItem } from '@/components/ui/segmented'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

import { apiPut, reason } from './http'
import {
  intentTypeLabel,
  type DatasourceList,
  type IndexStats,
  type JobStarted,
  type NonDataFaceList,
  type NonDataFacesSaveResult,
  type SchemaSnapshot,
  type SqlIntent,
  type SqlIntentDetail,
  type SqlIntentList,
} from './schema'

type Filter = 'all' | 'draft' | 'published' | 'disabled'

const FILTERS: Filter[] = ['all', 'draft', 'published', 'disabled']

export function IntentsPage() {
  const [filter, setFilter] = useState<Filter>('all')
  const [jobId, setJobId] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [confirmId, setConfirmId] = useState<string | null>(null)

  const intents = useApi<SqlIntentList>('/api/text2sql/intents', {
    // 生成 Job 在跑的时候这张表不会变(候选还在审核台上),所以只在采纳后靠 reload 拉一次
    refetchInterval: null,
  })
  const stats = useApi<IndexStats>('/api/text2sql/index-stats')
  const datasources = useApi<DatasourceList>('/api/text2sql/datasources')
  const ds = datasources.data?.items[0] ?? null

  const items = (intents.data?.items ?? []).filter(
    (it) => filter === 'all' || it.status === filter,
  )
  const count = (f: Filter) =>
    f === 'all'
      ? (intents.data?.items.length ?? 0)
      : (intents.data?.items.filter((it) => it.status === f).length ?? 0)

  const remove = async (it: SqlIntent) => {
    try {
      await apiDelete(`/api/text2sql/intents/${it.id}`)
      pushToast('success', 'Draft deleted', `${it.code} is gone; its candidate is reviewable again.`)
      intents.reload()
    } catch (e) {
      // 已发布/已下线的不许删(后端 409):它们可能被历史消息引用过
      pushToast('error', 'delete_failed', reason(e, 'Could not delete this intent.'))
    } finally {
      setConfirmId(null)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="-mt-1 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <Link
          to="/ingest/text2sql"
          className="text-secondary-foreground hover:text-primary flex items-center gap-1.5 text-[13px] transition-colors"
        >
          <ArrowLeft className="size-3.5" /> Datasources
        </Link>
        <span className="bg-kb-text2sql size-2.5 rounded-full" />
        <span className="text-[13px] font-semibold">Question intents</span>
        {stats.data && (
          // 索引面数是"检索能看见什么"的全部:摘要 + 问法 + 空路由负例
          <span className="text-faint font-mono text-[11px]">
            {stats.data.total} index faces · {stats.data.summary} summary ·{' '}
            {stats.data.question} question · {stats.data.non_data} non-data
          </span>
        )}
        <div className="ml-auto flex items-center gap-2.5">
          <Button size="sm" variant="secondary" onClick={() => setAdding((v) => !v)}>
            <Plus /> New intent
          </Button>
        </div>
      </div>

      {ds && <GenerateCard datasource={ds.id} onStarted={setJobId} />}

      {adding && (
        <NewIntentCard
          onCancel={() => setAdding(false)}
          onCreated={() => {
            setAdding(false)
            intents.reload()
          }}
        />
      )}

      {jobId && (
        <Card className="overflow-hidden">
          <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
            <Sparkles className="text-faint size-4" />
            <span className="text-[13px] font-semibold">Drafting intents</span>
            <button
              type="button"
              aria-label="Hide generation progress"
              className="text-fainter hover:bg-hover hover:text-foreground ml-auto flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
              onClick={() => {
                setJobId(null)
                intents.reload()
              }}
            >
              <X className="size-3.5" />
            </button>
          </div>
          {/* 采纳发生在审核台上(这块底下那个按钮),采纳完回到这一页就多出几条 draft */}
          <JobProgress jobId={jobId} />
        </Card>
      )}

      <Card className="overflow-hidden">
        <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
          <ListTree className="text-faint size-4" />
          <span className="text-[13px] font-semibold">Intents</span>
          <div className="ml-auto">
            <Segmented>
              {FILTERS.map((f) => (
                <SegmentedItem
                  key={f}
                  active={filter === f}
                  label={f}
                  count={count(f)}
                  onClick={() => setFilter(f)}
                />
              ))}
            </Segmented>
          </div>
        </div>
        <DataState
          state={intents}
          isEmpty={() => items.length === 0}
          emptyIcon={ListTree}
          emptyTitle={filter === 'all' ? 'No intent yet' : `No ${filter} intent`}
          emptyDescription={
            filter === 'all'
              ? 'Draft a batch from the governed schema above, then adopt the ones worth building.'
              : 'Switch the filter to see the other intents.'
          }
        >
          {() => (
            <Table>
              <THead>
                <TR>
                  {/* 列宽收得住:1280 下整张表要塞进卡片里,不靠横向滚动才看得见动作列 */}
                  <TH className="w-[58px]">Code</TH>
                  <TH className="w-[84px]">Type</TH>
                  <TH>Summary</TH>
                  <TH className="w-[120px]">Tables</TH>
                  <TH className="w-[120px]">Template</TH>
                  <TH className="w-[100px]">Status</TH>
                  <TH className="w-[92px]" />
                </TR>
              </THead>
              <tbody>
                {items.map((it) => (
                  <TR key={it.id}>
                    <TD className="font-mono text-[12px] font-medium">{it.code}</TD>
                    <TD>
                      <Badge tone={it.intent_type === 'stats' ? 'info' : 'navy'}>
                        {intentTypeLabel(it.intent_type)}
                      </Badge>
                    </TD>
                    <TD className="max-w-[296px]">
                      <Link
                        to={`/ingest/text2sql/intents/${it.id}`}
                        className="hover:text-primary block truncate text-[13.5px] font-medium transition-colors"
                      >
                        {it.one_liner}
                      </Link>
                      {it.bucket && (
                        <div className="text-faint mt-0.5 truncate text-[11px]">{it.bucket}</div>
                      )}
                    </TD>
                    <TD className="text-faint max-w-[120px] truncate font-mono text-[10.5px]">
                      {it.tables.join(' · ')}
                    </TD>
                    <TD className="font-mono text-[11px] whitespace-nowrap">
                      {/* "有 SQL"和"进了检索"是两件事,一格里分开说 */}
                      {it.has_sql ? (
                        <span className="text-success">sql ok</span>
                      ) : (
                        <span className="text-warning">no sql</span>
                      )}
                      <span className="text-faint">
                        {' · '}
                        {it.question_count}q
                      </span>
                      <span className={cn('', it.face_count ? 'text-primary' : 'text-ghost')}>
                        {' · '}
                        {it.face_count} faces
                      </span>
                    </TD>
                    <TD>
                      <StatusBadge status={it.status} />
                    </TD>
                    <TD className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link to={`/ingest/text2sql/intents/${it.id}`}>
                          <Button size="sm" variant={it.status === 'draft' ? 'primary' : 'secondary'}>
                            <Search /> Open
                          </Button>
                        </Link>
                        {/* 只有草稿能删(后端同理);已发布的走详情页的 Disable */}
                        {it.status === 'draft' &&
                          (confirmId === it.id ? (
                            <Button size="sm" variant="danger" onClick={() => void remove(it)}>
                              <Trash2 /> Delete
                            </Button>
                          ) : (
                            <button
                              type="button"
                              aria-label={`Delete ${it.code}`}
                              className="text-fainter hover:bg-destructive-hover hover:text-destructive flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
                              onClick={() => setConfirmId(it.id)}
                            >
                              <Trash2 className="size-3.5" />
                            </button>
                          ))}
                      </div>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </DataState>
      </Card>

      <NonDataFacesCard onSaved={() => stats.reload()} />
    </div>
  )
}

/** 批量生成候选。选表是刻意的:**只喂人想要的那几张表**,生成质量比"全库一把梭"高得多。 */
function GenerateCard({
  datasource,
  onStarted,
}: {
  datasource: string
  onStarted: (jobId: string) => void
}) {
  const [count, setCount] = useState(10)
  const [picked, setPicked] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)
  const schema = useApi<SchemaSnapshot>(`/api/text2sql/datasources/${datasource}/schema`)
  const tables = (schema.data?.tables ?? []).filter((t) => t.enabled)
  const selected = picked ?? tables.map((t) => t.table_name)

  // 用更新函数形式而不是读渲染时的 selected:同一批里点两下(或程序化连点)时,
  // 读闭包会让前一下丢掉 —— 浏览器自测时正是这么被抓出来的
  const toggle = (name: string) =>
    setPicked((cur) => {
      const base = cur ?? tables.map((t) => t.table_name)
      return base.includes(name) ? base.filter((n) => n !== name) : [...base, name]
    })

  const generate = async () => {
    setBusy(true)
    try {
      const job = await apiPost<JobStarted>(
        `/api/text2sql/datasources/${datasource}/intents`,
        { count, tables: selected },
      )
      onStarted(job.job_id)
      pushToast('success', 'Drafting started', 'Candidates land on the review board when it ends.')
    } catch (e) {
      pushToast('error', 'generate_failed', reason(e, 'Could not start the generation job.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
        <Sparkles className="text-faint size-4" />
        <span className="text-[13px] font-semibold">Draft intents from the semantic layer</span>
        <span className="text-faint ml-auto font-mono text-[11px]">
          {selected.length}/{tables.length} tables
        </span>
      </div>
      <div className="flex flex-col gap-5 px-[26px] py-[22px]">
        {tables.length === 0 ? (
          <p className="text-faint text-[12.5px] leading-[1.6]">
            No enabled table has been described yet. Govern the schema first — the generator reads
            nothing but the semantic layer.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5">
              {tables.map((t) => {
                const on = selected.includes(t.table_name)
                return (
                  <button
                    key={t.id}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggle(t.table_name)}
                    className={cn(
                      'flex h-8 items-center gap-1.5 rounded-[var(--radius-pill)] border px-3 font-mono text-[11.5px] transition-all duration-150',
                      on
                        ? 'border-selected-border bg-selected text-primary'
                        : 'text-faint hover:bg-subtle border-transparent',
                    )}
                  >
                    {on && <Check className="size-3" strokeWidth={3} />}
                    {t.table_name}
                  </button>
                )
              })}
            </div>
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex flex-col gap-2">
                <span className="text-[12.5px] font-semibold">How many</span>
                <Input
                  className="h-9 w-[90px] font-mono"
                  value={String(count)}
                  inputMode="numeric"
                  onChange={(e) =>
                    setCount(Math.min(30, Number(e.target.value.replace(/\D/g, '')) || 0))
                  }
                />
              </label>
              <Button
                variant="accent"
                disabled={busy || selected.length === 0 || count < 1}
                onClick={() => void generate()}
              >
                {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
                Draft {count} intents
              </Button>
              <p className="text-faint max-w-[420px] text-[11.5px] leading-[1.5]">
                Existing summaries are fed back into the prompt to avoid repeats, so running this
                again appends — it never touches the intents you already adopted.
              </p>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}

/** 手工新建:建出来是 draft,和采纳候选走同一条后路(模板要在详情页生成)。 */
function NewIntentCard({
  onCancel,
  onCreated,
}: {
  onCancel: () => void
  onCreated: () => void
}) {
  const [type, setType] = useState<'query' | 'stats'>('query')
  const [oneLiner, setOneLiner] = useState('')
  const [brief, setBrief] = useState('')
  const [tables, setTables] = useState('')
  const [saving, setSaving] = useState(false)
  const list = tables
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

  const save = async () => {
    setSaving(true)
    try {
      const it = await apiPost<SqlIntentDetail>('/api/text2sql/intents', {
        intent_type: type,
        one_liner: oneLiner,
        brief,
        tables: list,
      })
      pushToast('success', `Intent ${it.code} created`, 'Generate its SQL template next.')
      onCreated()
    } catch (e) {
      pushToast('error', 'create_failed', reason(e, 'Could not create this intent.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
        <Plus className="text-faint size-4" />
        <span className="text-[13px] font-semibold">New intent</span>
        <button
          type="button"
          aria-label="Cancel"
          className="text-fainter hover:bg-hover hover:text-foreground ml-auto flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
          onClick={onCancel}
        >
          <X className="size-3.5" />
        </button>
      </div>
      <div className="flex flex-col gap-5 px-[26px] py-[22px]">
        <div className="flex flex-wrap items-center gap-4">
          <Segmented>
            <SegmentedItem active={type === 'query'} label="Query" onClick={() => setType('query')} />
            <SegmentedItem active={type === 'stats'} label="Stats" onClick={() => setType('stats')} />
          </Segmented>
          <span className="text-faint text-[11.5px]">
            Stats groups and aggregates; Query lists rows.
          </span>
        </div>
        <label className="flex flex-col gap-2">
          <span className="text-[12.5px] font-semibold">Summary</span>
          <Input
            value={oneLiner}
            placeholder="Monthly revenue by state"
            onChange={(e) => setOneLiner(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-[12.5px] font-semibold">Brief</span>
          <Textarea
            rows={4}
            className="text-[13px]"
            value={brief}
            placeholder="What the SQL has to do, in business terms."
            onChange={(e) => setBrief(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-[12.5px] font-semibold">Tables</span>
          <Input
            className="font-mono text-[12.5px]"
            value={tables}
            placeholder="orders, order_items"
            onChange={(e) => setTables(e.target.value)}
          />
        </label>
        <div>
          <Button
            variant="accent"
            disabled={saving || !oneLiner || !brief || list.length === 0}
            onClick={() => void save()}
          >
            {saving ? <Loader2 className="animate-spin" /> : <Check />}
            Create draft
          </Button>
        </div>
      </div>
    </Card>
  )
}

/** 空路由负例面 —— kb 级资产,整组替换,保存即重建向量。 */
function NonDataFacesCard({ onSaved }: { onSaved: () => void }) {
  const faces = useApi<NonDataFaceList>('/api/text2sql/non-data-faces')
  const [draft, setDraft] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const stored = (faces.data?.items ?? []).map((f) => f.face_text).join('\n')
  const text = draft ?? stored
  const lines = text.split('\n').map((s) => s.trim()).filter(Boolean)

  const save = async () => {
    setSaving(true)
    try {
      const res = await apiPut<NonDataFacesSaveResult>('/api/text2sql/non-data-faces', {
        faces: lines,
      })
      setDraft(null)
      faces.reload()
      onSaved()
      pushToast('success', `${res.indexed} faces indexed`, 'The null route is rebuilt.')
    } catch (e) {
      pushToast('error', 'save_failed', reason(e, 'Could not save the non-data faces.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
        <ClipboardCheck className="text-faint size-4" />
        <span className="text-[13px] font-semibold">Null route · non-data faces</span>
        <span className="text-faint ml-auto font-mono text-[11px]">{lines.length} faces</span>
      </div>
      <div className="flex flex-col gap-4 px-[26px] py-[22px]">
        {/* 这一段不是提示,是这块面板存在的理由:阈值拦不住非问数问题,负例才拦得住 */}
        <div className="bg-warning-soft text-warning flex items-start gap-2 rounded-[var(--radius-panel)] px-4 py-2.5 text-[12px] leading-[1.55]">
          <AlertTriangle className="mt-px size-4 shrink-0" strokeWidth={1.75} />
          These are questions this knowledge base must NOT answer with SQL. They are indexed
          alongside the intents so a warranty question matches a negative face instead of the
          nearest template — raising the score threshold cannot do this job. Emptying the list
          turns the null route off.
        </div>
        <label className="flex flex-col gap-2">
          <span className="text-[12.5px] font-semibold">One question per line</span>
          <Textarea
            rows={8}
            className="text-[12.5px] leading-[1.8]"
            value={text}
            placeholder="What is the warranty period for the panels?"
            onChange={(e) => setDraft(e.target.value)}
          />
        </label>
        <div className="flex items-center gap-2.5">
          <Button
            variant="primary"
            size="sm"
            disabled={saving || draft === null}
            onClick={() => void save()}
          >
            {saving ? <Loader2 className="animate-spin" /> : <Check />}
            Save and reindex
          </Button>
          {draft !== null && (
            <Button variant="ghost" size="sm" onClick={() => setDraft(null)}>
              Revert
            </Button>
          )}
          <span className="text-faint ml-auto font-mono text-[11px]">
            <Database className="mr-1 inline size-3" />
            {faces.data?.total ?? 0} stored
          </span>
        </div>
      </div>
    </Card>
  )
}
