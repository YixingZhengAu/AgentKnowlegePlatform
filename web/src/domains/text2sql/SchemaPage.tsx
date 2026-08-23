/** D2 Schema 治理页 —— 语义层的编辑台。
 *
 * 这一页产出的东西就是后面所有 prompt 的**唯一供料**:表/列的业务描述、枚举字典、
 * 哪些表列进得了语义层。SQL 模板生成得好不好,一半在这里决定。
 *
 * 五个设计决定:
 *
 * 1. **按表保存,不逐格保存**。审描述是"看完一张表再存"的动作;逐格 PATCH 会把一次
 *    人工评审拆成几十个请求,中途失败还留下半改的表。所以草稿留在前端,Save 一次事务
 *    (`PUT /tables/{id}`)。切表不丢草稿 —— 左侧列表上有未保存标记。
 * 2. **左侧的启用开关是例外:它立即落库**。它不是文字编辑,是"这张表算不算数"的闸;
 *    在列表里放一个要等 Save 才生效的开关,读起来会像已经生效了。
 * 3. **单列的 AI 按钮也整表生成**。评审过的 prompt 是表级的(靠同表其他列、join 与
 *    采样值一起判断一列是什么),只喂一列会得到更差的描述 —— 那就不再是 B2 验收过的
 *    那个 prompt 了。所以按钮打的是同一个接口,只是**只回填那一格**。
 * 4. **AI 只给建议,不落库**。单点接口同步返回建议、填进草稿,人看过再 Save;
 *    批量走 Job(每张启用的表一次 gpt-5),进度用共享的 `<JobProgress>`。
 * 5. **采样值与枚举字典要看得见**。判断一句描述对不对,靠的是这一列真实长什么样;
 *    枚举列展示"值 → 含义",因为改写阶段真正需要的是这个,不是裸 string。
 */

import {
  AlertTriangle,
  ArrowLeft,
  Check,
  ListTree,
  Loader2,
  RotateCcw,
  Sparkles,
  Table2,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
import { JobProgress } from '@/components/JobProgress'
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
  connTarget,
  tableDescribed,
  type ColumnMeta,
  type DescribeSuggestion,
  type JobStarted,
  type Relation,
  type SchemaSnapshot,
  type TableDetail,
  type TableSave,
} from './schema'
import { Toggle } from './Toggle'

/** 描述模式:填空缺 / 全量重写。**fill 逐字保留人写过的东西**,所以它是默认。 */
type Mode = 'fill' | 'rewrite'

/** 一列的草稿:只存被改过的字段 —— 保存时也只发这些,没碰过的字段后端一个字不写。 */
type ColDraft = Partial<
  Pick<ColumnMeta, 'display_name' | 'description' | 'is_sensitive' | 'enabled'>
>
type TableDraft = {
  display_name?: string
  description?: string
  columns: Record<string, ColDraft>
}

export function SchemaPage() {
  const { datasourceId } = useParams<{ datasourceId: string }>()
  const path = `/api/text2sql/datasources/${datasourceId}/schema`
  const [selected, setSelected] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Record<string, TableDraft>>({})
  const [mode, setMode] = useState<Mode>('fill')
  const [jobId, setJobId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const schema = useApi<SchemaSnapshot>(path, {
    // 批量描述在跑的时候,已完成的表会一张张变绿(described 计数会动);跑完就停
    refetchInterval: () => (jobId ? 2000 : null),
  })

  const tables = schema.data?.tables ?? []
  const table = tables.find((t) => t.id === selected) ?? tables[0] ?? null
  const draft = table ? drafts[table.id] : undefined

  const patchTable = (id: string, patch: Partial<TableDraft>) =>
    setDrafts((d) => {
      const cur: TableDraft = d[id] ?? { columns: {} }
      // patch 里带 columns 就是整表建议:它有意覆盖这张表的列草稿
      return { ...d, [id]: { ...cur, ...patch } }
    })

  const patchColumn = (tableId: string, colId: string, patch: ColDraft) =>
    setDrafts((d) => {
      const cur = d[tableId] ?? { columns: {} }
      return {
        ...d,
        [tableId]: {
          ...cur,
          columns: { ...cur.columns, [colId]: { ...cur.columns[colId], ...patch } },
        },
      }
    })

  const dropDraft = (id: string) =>
    setDrafts((d) => Object.fromEntries(Object.entries(d).filter(([k]) => k !== id)))

  /** 左侧列表的启用开关:立即落库(见文件头设计决定 2)。 */
  const toggleTable = async (t: TableDetail, enabled: boolean) => {
    try {
      await apiPut<TableDetail>(`/api/text2sql/tables/${t.id}`, { enabled, columns: [] })
      schema.reload()
    } catch (e) {
      pushToast('error', 'save_failed', reason(e, 'Could not change this table.'))
    }
  }

  const save = async (t: TableDetail) => {
    const d = drafts[t.id]
    if (!d) return
    setBusy(true)
    try {
      const body: TableSave = { columns: [] }
      if (d.display_name !== undefined) body.display_name = d.display_name
      if (d.description !== undefined) body.description = d.description
      body.columns = Object.entries(d.columns).map(([id, c]) => ({ id, ...c }))
      await apiPut<TableDetail>(`/api/text2sql/tables/${t.id}`, body)
      dropDraft(t.id)
      schema.reload()
      pushToast('success', 'Table saved', `${t.table_name} is up to date.`)
    } catch (e) {
      pushToast('error', 'save_failed', reason(e, 'Could not save this table.'))
    } finally {
      setBusy(false)
    }
  }

  /** 单点 AI:整表生成建议 → 填进草稿。`only` 给了就只回填那一列(那一个 AI 按钮)。 */
  const describe = async (t: TableDetail, only?: string) => {
    setBusy(true)
    try {
      const s = await apiPost<DescribeSuggestion>(`/api/text2sql/tables/${t.id}/describe`, { mode })
      const byName = new Map(t.columns.map((c) => [c.column_name, c]))
      if (only) {
        const sug = s.columns.find((c) => c.column_name === only)
        const col = byName.get(only)
        if (!sug || !col) {
          pushToast('info', 'Nothing suggested', `The model returned no description for ${only}.`)
          return
        }
        patchColumn(t.id, col.id, {
          display_name: sug.display_name || col.display_name,
          description: sug.description,
        })
      } else {
        const columns: Record<string, ColDraft> = {}
        for (const sug of s.columns) {
          const col = byName.get(sug.column_name)
          if (!col) continue
          columns[col.id] = {
            display_name: sug.display_name || col.display_name || undefined,
            description: sug.description,
          }
        }
        patchTable(t.id, { description: s.description, columns })
      }
      pushToast('success', 'Suggestions filled in', 'Nothing is stored yet — review, then Save.')
    } catch (e) {
      pushToast('error', 'describe_failed', reason(e, 'Could not generate descriptions.'))
    } finally {
      setBusy(false)
    }
  }

  /** 批量 AI:每张启用的表一次 gpt-5,所以是 Job。 */
  const describeAll = async () => {
    setBusy(true)
    try {
      const job = await apiPost<JobStarted>(`/api/text2sql/datasources/${datasourceId}/describe`, {
        mode,
      })
      setJobId(job.job_id)
      pushToast('success', 'Describe started', 'One model call per enabled table.')
    } catch (e) {
      pushToast('error', 'describe_failed', reason(e, 'Could not start the describe job.'))
    } finally {
      setBusy(false)
    }
  }

  const dirtyCount = Object.keys(drafts).length

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
        <span className="text-[13px] font-semibold">
          {schema.data?.datasource.name ?? 'Semantic layer'}
        </span>
        {schema.data && (
          <span className="text-faint font-mono text-[11px]">
            {connTarget(schema.data.datasource)}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2.5">
          <Link to="/ingest/text2sql/intents">
            <Button size="sm" variant="ghost">
              <ListTree /> Question intents
            </Button>
          </Link>
          {/* 模式对两个 AI 入口都生效:单表按钮与批量 Job 用同一个语义 */}
          <Segmented>
            <SegmentedItem
              active={mode === 'fill'}
              label="Fill gaps"
              onClick={() => setMode('fill')}
            />
            <SegmentedItem
              active={mode === 'rewrite'}
              label="Rewrite all"
              onClick={() => setMode('rewrite')}
            />
          </Segmented>
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => void describeAll()}>
            {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
            Describe every table
          </Button>
        </div>
      </div>

      {/* 两个模式都会覆盖"已存的描述";fill 保住的是**库里的 DDL 注释**,不是人在这一页打的字
          (出处 `services/text2sql/semantic.py` 头部)。所以这句话必须写准,不能写成
          "fill 不会动你写的东西" —— 那会让人以为草稿区之外的东西也安全 */}
      <div className="bg-warning-soft text-warning flex items-start gap-2 rounded-[var(--radius-panel)] px-4 py-2.5 text-[12px] leading-[1.55]">
        <AlertTriangle className="mt-px size-4 shrink-0" strokeWidth={1.75} />
        {mode === 'fill'
          ? 'Fill gaps keeps each column comment that already exists in the database, word for word. Descriptions written on this page are still replaced — the model cannot tell them apart from its own.'
          : 'Rewrite all replaces every description, including the column comments that come from the database itself.'}
      </div>

      {jobId && (
        <Card className="overflow-hidden">
          <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
            <Sparkles className="text-faint size-4" />
            <span className="text-[13px] font-semibold">AI describe</span>
            <button
              type="button"
              aria-label="Hide describe progress"
              className="text-fainter hover:bg-hover hover:text-foreground ml-auto flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
              onClick={() => {
                setJobId(null)
                schema.reload()
              }}
            >
              <X className="size-3.5" />
            </button>
          </div>
          <JobProgress jobId={jobId} />
        </Card>
      )}

      <DataState
        state={schema}
        isEmpty={(d) => d.tables.length === 0}
        emptyIcon={Table2}
        emptyTitle="Nothing synced yet"
        emptyDescription="Run a schema sync on this datasource first — governance needs the physical facts."
      >
        {(data) => (
          <div className="flex flex-col items-start gap-5 lg:flex-row">
            {/* 左:表清单。一行说三件事 —— 叫什么、在不在语义层里、描述写完了没 */}
            <Card className="w-full shrink-0 overflow-hidden lg:w-[286px]">
              <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[18px]">
                <Table2 className="text-faint size-4" />
                <span className="text-[13px] font-semibold">Tables</span>
                <span className="text-faint ml-auto font-mono text-[11px]">
                  {data.tables.filter((t) => t.enabled).length}/{data.tables.length} on
                </span>
              </div>
              <ul className="flex flex-col gap-1 p-2.5">
                {data.tables.map((t) => (
                  <li key={t.id}>
                    <div
                      className={cn(
                        'flex items-center gap-2.5 rounded-[var(--radius-row)] px-2.5 py-2 transition-all duration-150',
                        t.id === table?.id
                          ? 'bg-selected border-selected-border border shadow-[var(--shadow-row)]'
                          : 'hover:bg-subtle border border-transparent',
                      )}
                    >
                      <button
                        type="button"
                        className="min-w-0 flex-1 text-left"
                        onClick={() => setSelected(t.id)}
                      >
                        <div className="flex items-center gap-1.5">
                          <span
                            className={cn(
                              'truncate font-mono text-[12.5px]',
                              t.id === table?.id ? 'text-primary font-medium' : '',
                              !t.enabled && 'text-fainter',
                            )}
                          >
                            {t.table_name}
                          </span>
                          {drafts[t.id] && (
                            <span className="bg-warning size-1.5 shrink-0 rounded-full" />
                          )}
                        </div>
                        <div className="text-faint mt-0.5 truncate text-[11px]">
                          {t.row_count_estimate != null && (
                            <span className="font-mono">
                              {t.row_count_estimate.toLocaleString('en-AU')} rows ·{' '}
                            </span>
                          )}
                          <span
                            className={cn(
                              'font-mono',
                              tableDescribed(t) ? 'text-success' : 'text-warning',
                            )}
                          >
                            {t.described_columns}/{t.column_count} described
                          </span>
                        </div>
                      </button>
                      <Toggle
                        checked={t.enabled}
                        onChange={(next) => void toggleTable(t, next)}
                        label={`Include ${t.table_name} in the semantic layer`}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            </Card>

            {/* 右:选中表的字段。这里是真正花时间的地方 */}
            {table && (
              <TablePanel
                table={table}
                draft={draft}
                relations={data.relations}
                busy={busy}
                dirtyCount={dirtyCount}
                onTableField={(patch) => patchTable(table.id, patch)}
                onColumnField={(colId, patch) => patchColumn(table.id, colId, patch)}
                onRevert={() => dropDraft(table.id)}
                onSave={() => void save(table)}
                onDescribe={(only) => void describe(table, only)}
              />
            )}
          </div>
        )}
      </DataState>
    </div>
  )
}

function TablePanel({
  table,
  draft,
  relations,
  busy,
  dirtyCount,
  onTableField,
  onColumnField,
  onRevert,
  onSave,
  onDescribe,
}: {
  table: TableDetail
  draft?: TableDraft
  relations: Relation[]
  busy: boolean
  dirtyCount: number
  onTableField: (patch: Partial<TableDraft>) => void
  onColumnField: (colId: string, patch: ColDraft) => void
  onRevert: () => void
  onSave: () => void
  onDescribe: (only?: string) => void
}) {
  const joins = useMemo(
    () =>
      relations.filter((r) => r.from_table === table.table_name || r.to_table === table.table_name),
    [relations, table.table_name],
  )
  const dirty = draft !== undefined
  const value = <K extends keyof TableDraft>(key: K) =>
    draft?.[key] !== undefined
      ? (draft[key] as string)
      : ((table[key as 'description'] as string) ?? '')

  return (
    <Card className="min-w-0 flex-1 overflow-hidden">
      <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
        <span className="font-mono text-[13px] font-medium">{table.table_name}</span>
        {!table.enabled && <Badge tone="neutral">excluded</Badge>}
        {dirty && <Badge tone="warning">unsaved</Badge>}
        <div className="ml-auto flex items-center gap-1.5">
          {dirty && (
            <Button size="sm" variant="ghost" onClick={onRevert}>
              <RotateCcw /> Revert
            </Button>
          )}
          <Button size="sm" variant="secondary" disabled={busy} onClick={() => onDescribe()}>
            {busy ? <Loader2 className="animate-spin" /> : <Sparkles />}
            Describe table
          </Button>
          <Button size="sm" variant="primary" disabled={!dirty || busy} onClick={onSave}>
            <Check /> Save table
          </Button>
        </div>
      </div>

      <div className="flex flex-col gap-5 px-[26px] py-[22px]">
        <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
          <label className="flex flex-col gap-2">
            <span className="text-[12.5px] font-semibold">Display name</span>
            <Input
              value={value('display_name')}
              placeholder={table.table_name}
              onChange={(e) => onTableField({ display_name: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-2">
            <span className="text-[12.5px] font-semibold">What one row of this table means</span>
            <Textarea
              rows={3}
              className="text-[13px]"
              value={value('description')}
              placeholder="One row represents…"
              onChange={(e) => onTableField({ description: e.target.value })}
            />
          </label>
        </div>
        {table.physical_comment && (
          <p className="text-faint text-[11.5px]">
            Comment in the database:{' '}
            <span className="font-mono text-[11px]">{table.physical_comment}</span>
          </p>
        )}
      </div>

      <Table>
        <THead>
          <TR>
            <TH className="w-[220px]">Column</TH>
            <TH className="w-[170px]">Display name</TH>
            <TH>Description</TH>
            <TH className="w-[220px]">Values</TH>
            <TH className="w-[80px]">Sensitive</TH>
            <TH className="w-[60px]">On</TH>
            <TH className="w-[46px]" />
          </TR>
        </THead>
        <tbody>
          {table.columns.map((c) => {
            const d = draft?.columns[c.id]
            const text = (key: 'display_name' | 'description') =>
              d?.[key] !== undefined ? (d[key] as string) : (c[key] ?? '')
            const flag = (key: 'is_sensitive' | 'enabled') => d?.[key] ?? c[key]
            return (
              <TR key={c.id}>
                <TD className="align-top">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[12.5px] font-medium">{c.column_name}</span>
                    {c.key_flag === 'PRI' && <Badge tone="navy">pk</Badge>}
                    {c.key_flag === 'UNI' && <Badge tone="neutral">unique</Badge>}
                  </div>
                  <div className="text-faint mt-1 font-mono text-[10.5px]">
                    {c.data_type}
                    {c.is_nullable ? ' · null' : ''}
                    {c.distinct_count != null ? ` · ${c.distinct_count} distinct` : ''}
                  </div>
                </TD>
                <TD className="align-top">
                  <Input
                    className="h-8 px-3 text-[12.5px]"
                    value={text('display_name')}
                    placeholder={c.column_name}
                    onChange={(e) => onColumnField(c.id, { display_name: e.target.value })}
                  />
                </TD>
                <TD className="align-top">
                  <Textarea
                    rows={2}
                    className="px-3 py-2 text-[12.5px] leading-[1.55]"
                    value={text('description')}
                    placeholder="What this column means in business terms"
                    onChange={(e) => onColumnField(c.id, { description: e.target.value })}
                  />
                </TD>
                <TD className="align-top">
                  <ColumnValues column={c} />
                </TD>
                <TD className="align-top">
                  <Toggle
                    tone="danger"
                    checked={flag('is_sensitive')}
                    onChange={(next) => onColumnField(c.id, { is_sensitive: next })}
                    label={`Mark ${c.column_name} as sensitive`}
                  />
                </TD>
                <TD className="align-top">
                  <Toggle
                    checked={flag('enabled')}
                    onChange={(next) => onColumnField(c.id, { enabled: next })}
                    label={`Include ${c.column_name} in the semantic layer`}
                  />
                </TD>
                <TD className="text-right align-top">
                  <button
                    type="button"
                    disabled={busy}
                    // 打的是整表接口(见文件头设计决定 3),只回填这一格
                    title={`Describe ${c.column_name}. The model reads the whole table, only this row is filled in.`}
                    aria-label={`Describe ${c.column_name} with AI`}
                    className="text-fainter hover:bg-primary-soft hover:text-primary flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150 disabled:cursor-not-allowed"
                    onClick={() => onDescribe(c.column_name)}
                  >
                    <Sparkles className="size-3.5" />
                  </button>
                </TD>
              </TR>
            )
          })}
        </tbody>
      </Table>

      {joins.length > 0 && (
        <div className="border-t border-[var(--border-soft)] px-[26px] py-[18px]">
          <div className="text-muted-foreground mb-2.5 text-[11px] font-semibold tracking-[0.06em] uppercase">
            Join hints
          </div>
          <ul className="flex flex-col gap-1.5">
            {joins.map((r) => (
              <li key={r.id} className="flex items-center gap-2 font-mono text-[11px]">
                <span>
                  {r.from_table}.{r.from_column} → {r.to_table}.{r.to_column}
                </span>
                {/* 真 FK 与命名启发式猜出来的可信度不同,这里必须分得开
                    (取值出处 `models/text2sql.py` 的 RELATION_SOURCES) */}
                <Badge tone={r.source === 'foreign_key' ? 'success' : 'warning'}>{r.source}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}

      {dirtyCount > 1 && (
        <div className="text-faint border-t border-[var(--border-soft)] px-[26px] py-3 text-[11.5px]">
          {dirtyCount} tables have unsaved edits. Each table is saved on its own.
        </div>
      )}
    </Card>
  )
}

/** 采样值与枚举字典:判断一句描述对不对,靠的就是这一列真实长什么样。 */
function ColumnValues({ column }: { column: ColumnMeta }) {
  if (column.is_enum_like && column.enum_values?.length) {
    return (
      <ul className="flex flex-col gap-1">
        {column.enum_values.map((v) => (
          <li key={v.value} className="text-[11px] leading-[1.4]">
            <span className="text-foreground font-mono">{v.value}</span>
            {v.meaning && <span className="text-faint"> — {v.meaning}</span>}
          </li>
        ))}
      </ul>
    )
  }
  if (!column.sample_values?.length)
    return <span className="text-ghost font-mono text-[11px]">—</span>
  return (
    <div className="text-faint font-mono text-[10.5px] leading-[1.5] break-all">
      {column.sample_values.slice(0, 4).join(', ')}
    </div>
  )
}
