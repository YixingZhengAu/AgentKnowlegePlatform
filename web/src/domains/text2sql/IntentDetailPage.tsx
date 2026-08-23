/** D4 意图详情页 —— 一条模板从"值得做"走到"我验收了"的全部工作都在这一页。
 *
 * 页面顺序就是人的工作顺序:**意图信息 → SQL 模板 → 三区参数 → 相似问法 → 发布**。
 *
 * 六个设计决定:
 *
 * 1. **一张卡片一次保存**。四块内容打的是四个不同的后端动作(PATCH 意图 /
 *    PATCH sql / PATCH params / PUT questions),真按一个"全保存"会变成四个请求的
 *    半成功状态。所以每张卡片自己管草稿、自己有 Save,标题栏上带 `unsaved`。
 * 2. **生成模板是"整条替换",按钮上必须写清**。`POST …/template` 走完 B4+B5 全链路
 *    (生成 → 9 条静态校验 → 真库试执行 → 报错自修 → AST 拆参数 → AI 预填),
 *    返回时 SQL 与参数区已经落库 —— 人手改过的 hint 也会没。所以它单独一句红字。
 * 3. **Run 打的是运行时那道执行闸**,不是另一条通路。所以"Run 过了"含义明确:
 *    这条 SQL 在运行时不会因为闸(非单条 SELECT / 表列不在白名单 / LIMIT / 超时)而失败。
 *    SQL 报错是 200 + `ok=false`,它是这个接口要**报告**的结果,不是请求出错。
 * 4. **参数区重解析是纯代码、零 LLM**,按 `param_id` 保住人写过的业务名与 hint。
 *    它读的是**库里那条 SQL**,所以 SQL 有未保存改动时这个按钮是灰的 —— 否则会拿旧
 *    SQL 解析出一份对不上的参数区。
 * 5. **相似问法保存即重建索引面**(意图已发布时)。所以这张卡片上要把"几条问法 →
 *    几个索引面"摆出来:每一条问法就是一行向量,删一条就是少一个能被命中的说法。
 * 6. **发布按钮变灰要给原因**。原因一律来自后端 `publish_blockers`,前端一个字不自己编
 *    (那套校验只有一处出处:`services/text2sql/publisher.py`)。
 */

import {
  AlertTriangle,
  ArrowLeft,
  BadgeCheck,
  Ban,
  Check,
  ClipboardCopy,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
  SquareCode,
  Wand2,
} from 'lucide-react'
import { Fragment, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { apiPatch, apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
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
  paramCount,
  publishable,
  type IntentParams,
  type IntentPublishResult,
  type ParamFilter,
  type ParamGroupBy,
  type ParamOutput,
  type ParseParamsResult,
  type QuestionsGenerated,
  type QuestionsSaveResult,
  type RunResult,
  type SqlIntentDetail,
  type TemplateDesign,
  type TemplateResult,
} from './schema'
import { SqlEditor } from './SqlEditor'

/** AI 生成相似问法的条数(后端默认值同为 8:`questions.DEFAULT_N`)。 */
const QUESTIONS_N = 8

export function IntentDetailPage() {
  const { intentId } = useParams<{ intentId: string }>()
  const detail = useApi<SqlIntentDetail>(`/api/text2sql/intents/${intentId}`)

  return (
    <div className="flex flex-col gap-5">
      <div className="-mt-1 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <Link
          to="/ingest/text2sql/intents"
          className="text-secondary-foreground hover:text-primary flex items-center gap-1.5 text-[13px] transition-colors"
        >
          <ArrowLeft className="size-3.5" /> Intents
        </Link>
        <span className="bg-kb-text2sql size-2.5 rounded-full" />
        <span className="font-mono text-[13px] font-semibold">{detail.data?.code ?? '…'}</span>
        {detail.data && (
          <>
            <Badge tone={detail.data.intent_type === 'stats' ? 'info' : 'navy'}>
              {intentTypeLabel(detail.data.intent_type)}
            </Badge>
            <StatusBadge status={detail.data.status} />
            {detail.data.human_edited && <Badge tone="neutral">human edited</Badge>}
          </>
        )}
      </div>

      <DataState
        state={detail}
        emptyIcon={SquareCode}
        emptyTitle="Intent not found"
        emptyDescription="It may have been deleted from the intents list."
      >
        {(it) => (
          <>
            <PublishBar intent={it} onDone={detail.reload} />
            <InfoCard intent={it} onSaved={detail.reload} />
            <TemplateCard intent={it} onSaved={detail.reload} />
            <ParamsCard intent={it} onSaved={detail.reload} />
            <QuestionsCard intent={it} onSaved={detail.reload} />
          </>
        )}
      </DataState>
    </div>
  )
}

/** 发布 / 下线 + 变灰原因。发布才建索引面,所以这一条要显示"建了几个面"。 */
function PublishBar({ intent, onDone }: { intent: SqlIntentDetail; onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const ok = publishable(intent)

  const act = async (what: 'publish' | 'disable') => {
    setBusy(true)
    try {
      const res = await apiPost<IntentPublishResult>(
        `/api/text2sql/intents/${intent.id}/${what}`,
      )
      pushToast(
        'success',
        what === 'publish' ? `${res.code} published` : `${res.code} disabled`,
        what === 'publish'
          ? `${res.faces} index faces built · ${res.non_data_faces} non-data faces rebuilt.`
          : 'Its index faces are gone; the intent row is kept.',
      )
      onDone()
    } catch (e) {
      pushToast('error', `${what}_failed`, reason(e, `Could not ${what} this intent.`))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-wrap items-center gap-[18px] px-[26px] py-[18px]">
      <div className="min-w-0 flex-1">
        <div className="font-display mb-1 text-[14px] font-bold tracking-[-0.01em]">
          {intent.status === 'published' ? 'Live in retrieval' : 'Not in retrieval yet'}
        </div>
        {ok ? (
          <p className="text-faint text-[12px] leading-[1.5]">
            {intent.status === 'published'
              ? `${intent.face_count} index faces · ${intent.question_count} similar questions. Re-publish after editing the SQL.`
              : 'Publishing builds this intent’s index faces and rebuilds the null route.'}
          </p>
        ) : (
          // 原因来自后端,原样显示 —— 校验只有一处出处
          <ul className="flex flex-col gap-1">
            {intent.publish_blockers.map((b) => (
              <li key={b} className="text-warning flex items-start gap-1.5 text-[12px]">
                <AlertTriangle className="mt-px size-3.5 shrink-0" strokeWidth={1.75} />
                {b}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex items-center gap-2.5">
        {intent.status === 'published' && (
          <Button variant="secondary" disabled={busy} onClick={() => void act('disable')}>
            <Ban /> Disable
          </Button>
        )}
        <Button variant="accent" disabled={busy || !ok} onClick={() => void act('publish')}>
          {busy ? <Loader2 className="animate-spin" /> : <BadgeCheck />}
          {intent.status === 'published' ? 'Re-publish' : 'Publish'}
        </Button>
      </div>
    </Card>
  )
}

/** 意图信息。★ 改摘要会影响检索(它本身就是一个索引面),已发布时后端会顺手重建面。 */
function InfoCard({ intent, onSaved }: { intent: SqlIntentDetail; onSaved: () => void }) {
  const [draft, setDraft] = useState<Partial<SqlIntentDetail> | null>(null)
  const [busy, setBusy] = useState(false)
  const v = <K extends 'one_liner' | 'brief' | 'bucket' | 'intent_type'>(k: K) =>
    (draft?.[k] ?? intent[k] ?? '') as string
  const tables = draft?.tables ?? intent.tables
  const dirty = draft !== null
  const patch = (p: Partial<SqlIntentDetail>) => setDraft((d) => ({ ...(d ?? {}), ...p }))

  const save = async () => {
    if (!draft) return
    setBusy(true)
    try {
      await apiPatch<SqlIntentDetail>(`/api/text2sql/intents/${intent.id}`, draft)
      setDraft(null)
      onSaved()
      pushToast(
        'success',
        'Intent saved',
        intent.status === 'published' && draft.one_liner
          ? 'The summary is an index face, so retrieval was rebuilt.'
          : 'Nothing else was touched.',
      )
    } catch (e) {
      pushToast('error', 'save_failed', reason(e, 'Could not save this intent.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <CardShell
      icon={SquareCode}
      title="Intent"
      dirty={dirty}
      right={
        <>
          {dirty && (
            <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
              <RotateCcw /> Revert
            </Button>
          )}
          <Button size="sm" variant="primary" disabled={!dirty || busy} onClick={() => void save()}>
            <Check /> Save intent
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5 px-[26px] py-[22px]">
        <div className="flex flex-wrap items-center gap-4">
          <Segmented>
            <SegmentedItem
              active={v('intent_type') === 'query'}
              label="Query"
              onClick={() => patch({ intent_type: 'query' })}
            />
            <SegmentedItem
              active={v('intent_type') === 'stats'}
              label="Stats"
              onClick={() => patch({ intent_type: 'stats' })}
            />
          </Segmented>
          <span className="text-faint text-[11.5px]">
            Stats groups and aggregates; Query lists rows.
          </span>
        </div>
        <label className="flex flex-col gap-2">
          <span className="text-[12.5px] font-semibold">Summary</span>
          <Input value={v('one_liner')} onChange={(e) => patch({ one_liner: e.target.value })} />
          <span className="text-faint text-[11.5px]">
            This line is itself an index face — editing it changes how the intent is matched.
          </span>
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-[12.5px] font-semibold">Brief</span>
          <Textarea
            rows={4}
            className="text-[13px] leading-[1.7]"
            value={v('brief')}
            onChange={(e) => patch({ brief: e.target.value })}
          />
          <span className="text-faint text-[11.5px]">
            The template generator reads nothing but this and the semantic layer.
          </span>
        </label>
        <div className="grid gap-5 lg:grid-cols-[1fr_240px]">
          <label className="flex flex-col gap-2">
            <span className="text-[12.5px] font-semibold">Tables</span>
            <Input
              className="font-mono text-[12.5px]"
              value={tables.join(', ')}
              onChange={(e) =>
                patch({
                  tables: e.target.value
                    .split(',')
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
            />
          </label>
          <label className="flex flex-col gap-2">
            <span className="text-[12.5px] font-semibold">Bucket</span>
            <Input value={v('bucket')} onChange={(e) => patch({ bucket: e.target.value })} />
          </label>
        </div>
      </div>
    </CardShell>
  )
}

/** SQL 模板 + Run。这张卡是这一页的重心。 */
function TemplateCard({ intent, onSaved }: { intent: SqlIntentDetail; onSaved: () => void }) {
  const [draft, setDraft] = useState<string | null>(null)
  const [busy, setBusy] = useState<'gen' | 'run' | 'save' | 'parse' | null>(null)
  const [run, setRun] = useState<RunResult | null>(null)
  // 生成链路里那一次试执行 vs 人点 Run:同一个面板,但来源要说清(见 generate())
  const [trial, setTrial] = useState(false)
  const [design, setDesign] = useState<TemplateDesign | null>(null)
  const sql = draft ?? intent.sql ?? ''
  const dirty = draft !== null && draft !== (intent.sql ?? '')

  const generate = async () => {
    setBusy('gen')
    try {
      const res = await apiPost<TemplateResult>(`/api/text2sql/intents/${intent.id}/template`)
      setDraft(null)
      setDesign(res.design)
      // 试执行是生成链路里那一次真库执行,不是前端另发的一次 Run —— 原样摆出来。
      // sql_executed 留空:那条 SQL 就在上面的编辑器里,重复摆一遍反而像"闸改写过它"
      setTrial(true)
      setRun({
        ok: true,
        cols: res.trial_cols,
        rows: res.trial_rows as unknown[][],
        rowcount: res.trial_rowcount,
        flags: [],
        sql_executed: null,
        error: null,
      })
      onSaved()
      pushToast(
        'success',
        'Template generated',
        `${res.repair_rounds} repair rounds · ${res.prefill_rounds} prefill rounds · ` +
          `${res.trial_rowcount} rows on the trial run.`,
      )
    } catch (e) {
      pushToast('error', 'template_failed', reason(e, 'Could not generate the SQL template.'))
    } finally {
      setBusy(null)
    }
  }

  const save = async () => {
    setBusy('save')
    try {
      await apiPatch<SqlIntentDetail>(`/api/text2sql/intents/${intent.id}`, { sql })
      setDraft(null)
      onSaved()
      pushToast('success', 'SQL saved', 'Re-parse the parameters if the shape changed.')
    } catch (e) {
      pushToast('error', 'save_failed', reason(e, 'Could not save the SQL.'))
    } finally {
      setBusy(null)
    }
  }

  const doRun = async () => {
    setBusy('run')
    try {
      // 连不上 / SQL 写错 / 被闸拒都是 200 + ok=false —— 这才是这个接口要报告的东西
      setTrial(false)
      setRun(await apiPost<RunResult>(`/api/text2sql/intents/${intent.id}/run`, { sql }))
    } catch (e) {
      pushToast('error', 'run_failed', reason(e, 'Could not run this SQL.'))
    } finally {
      setBusy(null)
    }
  }

  const reparse = async () => {
    setBusy('parse')
    try {
      const res = await apiPost<ParseParamsResult>(
        `/api/text2sql/intents/${intent.id}/parse-params`,
      )
      onSaved()
      pushToast(
        'success',
        'Parameters re-parsed',
        `${paramCount(res.params)} parameters · ${res.kept_annotations} annotations kept.`,
      )
    } catch (e) {
      // 最常见的一种:人手改坏了 SQL(投影没起别名、过滤列不在语义层)—— 后端会说是哪一处
      pushToast('error', 'parse_failed', reason(e, 'Could not parse the parameters.'))
    } finally {
      setBusy(null)
    }
  }

  return (
    <CardShell
      icon={SquareCode}
      title="SQL template"
      dirty={dirty}
      right={
        <>
          <Button
            size="sm"
            variant="secondary"
            disabled={busy !== null}
            onClick={() => void generate()}
          >
            {busy === 'gen' ? <Loader2 className="animate-spin" /> : <Wand2 />}
            {intent.sql ? 'Regenerate' : 'Generate template'}
          </Button>
          <Button size="sm" variant="secondary" disabled={busy !== null || !sql} onClick={() => void doRun()}>
            {busy === 'run' ? <Loader2 className="animate-spin" /> : <Play />}
            Run
          </Button>
          <Button size="sm" variant="primary" disabled={!dirty || busy !== null} onClick={() => void save()}>
            <Check /> Save SQL
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4 px-[26px] py-[22px]">
        {/* 重生成是整条替换 —— 这句话必须在按钮旁边,不能只写在文档里 */}
        {intent.sql && (
          <div className="text-warning flex items-start gap-2 text-[11.5px] leading-[1.5]">
            <AlertTriangle className="mt-px size-3.5 shrink-0" strokeWidth={1.75} />
            Regenerating replaces this SQL and the whole parameter section, including hints you
            wrote by hand.
          </div>
        )}

        {sql ? (
          <SqlEditor
            value={sql}
            label="SQL template"
            disabled={busy === 'gen'}
            onChange={(next) => setDraft(next)}
          />
        ) : (
          <p className="text-faint text-[12.5px] leading-[1.6]">
            No SQL yet. Generating runs the whole reviewed chain: draft → 9 static checks → a real
            trial execution → self-repair on errors → parameter parsing → AI prefill. It takes a
            while and costs several model calls, so it is one click per intent.
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            size="sm"
            variant="ghost"
            disabled={busy !== null || dirty || !intent.sql}
            onClick={() => void reparse()}
          >
            {busy === 'parse' ? <Loader2 className="animate-spin" /> : <RotateCcw />}
            Re-parse parameters
          </Button>
          <span className="text-faint text-[11.5px]">
            {dirty
              ? 'Save the SQL first — re-parsing reads the stored template, not the editor.'
              : 'Pure code, no model call. Business names and hints are kept by param id.'}
          </span>
        </div>

        {design && <DesignPanel design={design} />}

        {run && <RunPanel result={run} trial={trial} />}
      </div>
    </CardShell>
  )
}

/** 生成器的设计说明 —— **评审材料**:join 走哪条路、度量什么口径、哪些过滤被写死、凭什么。
 *
 *  写死的过滤条件是这一块最该被人看见的东西:它在运行时是改不动的
 *  (不在参数区就不在权力清单里),所以"为什么写死"必须当场能读到。 */
function DesignPanel({ design }: { design: TemplateDesign }) {
  const rows: { label: string; body: React.ReactNode }[] = []
  if (design.join_path) {
    rows.push({ label: 'join path', body: <Mono>{design.join_path}</Mono> })
  }
  if (design.measures?.length) {
    rows.push({
      label: 'measures',
      body: (
        <ul className="flex flex-col gap-1">
          {design.measures.map((m, i) => (
            <li key={i}>
              <Mono>{m.expr}</Mono>
              <span className="text-faint"> — {m.meaning}</span>
            </li>
          ))}
        </ul>
      ),
    })
  }
  if (design.group_by_dims?.length) {
    rows.push({ label: 'group by', body: <Mono>{design.group_by_dims.join(', ')}</Mono> })
  }
  if (design.default_filters?.length) {
    rows.push({
      label: 'baked-in filters',
      body: (
        <ul className="flex flex-col gap-1">
          {design.default_filters.map((f, i) => (
            <li key={i}>
              <Mono>{`${f.column} ${f.operator} ${f.value}`}</Mono>
              <span className="text-faint"> — {f.why}</span>
            </li>
          ))}
        </ul>
      ),
    })
  }
  if (design.caliber_notes?.length) {
    rows.push({
      label: 'caliber',
      body: (
        <ul className="flex flex-col gap-1">
          {design.caliber_notes.map((n, i) => (
            <li key={i} className="text-faint">
              {n}
            </li>
          ))}
        </ul>
      ),
    })
  }
  if (rows.length === 0) return null
  return (
    <div className="bg-subtle rounded-[var(--radius-panel)] px-4 py-3.5">
      <div className="text-fainter mb-2.5 font-mono text-[10.5px] tracking-[0.06em] uppercase">
        generator notes
      </div>
      <div className="grid gap-x-4 gap-y-2 sm:grid-cols-[104px_1fr]">
        {rows.map((r) => (
          <Fragment key={r.label}>
            <div className="text-faint text-[11.5px]">{r.label}</div>
            <div className="min-w-0 text-[12px] leading-[1.6]">{r.body}</div>
          </Fragment>
        ))}
      </div>
    </div>
  )
}

function Mono({ children }: { children: React.ReactNode }) {
  return <span className="font-mono text-[11.5px] break-all">{children}</span>
}

/** Run 结果:要么是数据,要么是一句原样的报错。**都不是异常**。 */
function RunPanel({ result, trial }: { result: RunResult; trial: boolean }) {
  const [showSql, setShowSql] = useState(false)
  if (!result.ok) {
    return (
      <div className="border-destructive-border rounded-[var(--radius-panel)] border px-4 py-3.5">
        <div className="text-destructive mb-1 flex items-center gap-2 text-[12.5px] font-semibold">
          <AlertTriangle className="size-4" strokeWidth={2} /> This SQL did not run
        </div>
        <p className="text-destructive-ink font-mono text-[11px] leading-[1.6] break-all">
          {result.error}
        </p>
      </div>
    )
  }
  return (
    <div className="overflow-hidden rounded-[var(--radius-panel)] border border-[var(--border-soft)]">
      <div className="flex flex-wrap items-center gap-2.5 border-b border-[var(--border-soft)] px-4 py-2.5">
        <span className="text-success flex items-center gap-1.5 text-[12.5px] font-semibold">
          <Check className="size-4" strokeWidth={2.25} /> {result.rowcount} rows
        </span>
        {trial && (
          <span className="text-faint text-[11.5px]">
            trial run from the generator — the template only passed because this came back non-empty
          </span>
        )}
        {result.flags.map((f) => (
          // 闸的动作要看得见:强制加过 LIMIT、截断过行数,都在这里
          <Badge key={f} tone="warning">
            {f}
          </Badge>
        ))}
        {result.sql_executed && (
          <button
            type="button"
            className="text-info ml-auto text-[12px] hover:underline"
            onClick={() => setShowSql((v) => !v)}
          >
            {showSql ? 'Hide executed SQL' : 'Show executed SQL'}
          </button>
        )}
      </div>
      {showSql && (
        <pre className="bg-subtle m-0 overflow-auto px-4 py-3 font-mono text-[11px] leading-[1.7] whitespace-pre-wrap">
          {result.sql_executed}
        </pre>
      )}
      <div className="max-h-[320px] overflow-auto">
        <Table>
          <THead>
            <TR>
              {result.cols.map((c) => (
                <TH key={c}>{c}</TH>
              ))}
            </TR>
          </THead>
          <tbody>
            {result.rows.map((row, i) => (
              <TR key={i}>
                {row.map((cell, j) => (
                  <TD key={j} className="font-mono text-[11.5px] whitespace-nowrap">
                    {cell === null ? <span className="text-ghost">null</span> : String(cell)}
                  </TD>
                ))}
              </TR>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  )
}

/** 三区参数 = 运行时权力的完整清单。这里编辑的是**业务名与 hint**,不是结构。 */
function ParamsCard({ intent, onSaved }: { intent: SqlIntentDetail; onSaved: () => void }) {
  const [draft, setDraft] = useState<IntentParams | null>(null)
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const params = draft ?? intent.params
  const dirty = draft !== null

  const edit = (
    zone: 'filters' | 'outputs' | 'groupbys',
    paramId: string,
    patch: { business_name?: string; hint?: string },
  ) =>
    setDraft(() => {
      const base = draft ?? intent.params
      return {
        ...base,
        [zone]: base[zone].map((p) => (p.param_id === paramId ? { ...p, ...patch } : p)),
      } as IntentParams
    })

  const save = async () => {
    if (!draft) return
    setBusy(true)
    try {
      await apiPatch<SqlIntentDetail>(`/api/text2sql/intents/${intent.id}`, { params: draft })
      setDraft(null)
      onSaved()
      pushToast('success', 'Parameters saved', 'The rewrite model reads these hints at query time.')
    } catch (e) {
      pushToast('error', 'save_failed', reason(e, 'Could not save the parameters.'))
    } finally {
      setBusy(false)
    }
  }

  const total = paramCount(params)

  return (
    <CardShell
      icon={Wand2}
      title="Parameters"
      dirty={dirty}
      count={`${total} in 3 zones`}
      right={
        <>
          {dirty && (
            <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
              <RotateCcw /> Revert
            </Button>
          )}
          <Button size="sm" variant="primary" disabled={!dirty || busy} onClick={() => void save()}>
            <Check /> Save parameters
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4 px-[26px] py-[22px]">
        <p className="text-faint text-[12px] leading-[1.6]">
          At query time the model may only change filter values, drop output columns and drop group
          keys — nothing else. Anything outside these three zones is refused, so this list is the
          complete set of what a question is allowed to move.
        </p>
        {total === 0 ? (
          <p className="text-ghost text-[12.5px]">
            No parameter section yet. Generate the SQL template, or re-parse an existing one.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {params.filters.map((p) => (
              <ParamRow
                key={p.param_id}
                id={p.param_id}
                zone="filter"
                head={`${p.source} ${p.operator}`}
                facts={[p.value_type, p.value_shape, p.predicate_sql].filter(Boolean) as string[]}
                param={p}
                open={open === p.param_id}
                onOpen={() => setOpen(open === p.param_id ? null : p.param_id)}
                onEdit={(patch) => edit('filters', p.param_id, patch)}
              />
            ))}
            {params.outputs.map((p) => (
              <ParamRow
                key={p.param_id}
                id={p.param_id}
                zone="output"
                head={p.alias}
                facts={[p.expr, p.source].filter(Boolean) as string[]}
                param={p}
                open={open === p.param_id}
                onOpen={() => setOpen(open === p.param_id ? null : p.param_id)}
                onEdit={(patch) => edit('outputs', p.param_id, patch)}
              />
            ))}
            {params.groupbys.map((p) => (
              <ParamRow
                key={p.param_id}
                id={p.param_id}
                zone="group by"
                head={p.expr}
                facts={
                  [p.source, p.linked_output ? `drops with ${p.linked_output}` : ''].filter(
                    Boolean,
                  ) as string[]
                }
                param={p}
                open={open === p.param_id}
                onOpen={() => setOpen(open === p.param_id ? null : p.param_id)}
                onEdit={(patch) => edit('groupbys', p.param_id, patch)}
              />
            ))}
          </div>
        )}
      </div>
    </CardShell>
  )
}

/** 一个参数一张折叠卡(交互参考 `tmp/sql definition.png`):
 *  收起时是"标识 + 物理事实",展开才编辑业务名与 hint。 */
function ParamRow({
  id,
  zone,
  head,
  facts,
  param,
  open,
  onOpen,
  onEdit,
}: {
  id: string
  zone: string
  head: string
  facts: string[]
  param: ParamFilter | ParamOutput | ParamGroupBy
  open: boolean
  onOpen: () => void
  onEdit: (patch: { business_name?: string; hint?: string }) => void
}) {
  const annotated = Boolean(param.business_name || param.hint)
  return (
    <div
      className={cn(
        'rounded-[var(--radius-panel)] border transition-all duration-150',
        open ? 'border-selected-border bg-selected' : 'hover:bg-subtle border-transparent',
      )}
    >
      <button
        type="button"
        className="flex w-full items-center gap-2.5 px-4 py-2.5 text-left"
        onClick={onOpen}
      >
        <Badge tone={zone === 'filter' ? 'navy' : zone === 'output' ? 'info' : 'neutral'}>
          {zone}
        </Badge>
        <span className="font-mono text-[12px] font-medium">{id}</span>
        <span className="text-faint truncate font-mono text-[11px]">{head}</span>
        <span className="ml-auto shrink-0 text-[11.5px]">
          {annotated ? (
            <span className="text-success">{param.business_name || 'annotated'}</span>
          ) : (
            // hint 是给改写模型看的取值说明书:空着不是"没写注释",是运行时少一份判断依据
            <span className="text-warning">no hint</span>
          )}
        </span>
      </button>
      {open && (
        <div className="flex flex-col gap-4 px-4 pb-4">
          <div className="text-faint flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10.5px]">
            {facts.map((f) => (
              <span key={f}>{f}</span>
            ))}
          </div>
          <label className="flex flex-col gap-2">
            <span className="text-[12px] font-semibold">Business name</span>
            <Input
              className="h-8 px-3 text-[12.5px]"
              value={param.business_name}
              placeholder="What a person would call this"
              onChange={(e) => onEdit({ business_name: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-2">
            <span className="text-[12px] font-semibold">Hint</span>
            <Textarea
              rows={3}
              className="px-3 py-2 text-[12px] leading-[1.6]"
              value={param.hint}
              placeholder="Accepted values, format, default, and when it must not be changed."
              onChange={(e) => onEdit({ hint: e.target.value })}
            />
            <span className="text-faint text-[11px] leading-[1.45]">
              This is a value manual for the rewrite model, not a comment: formats, enum values,
              defaults, and the cases where it must stay put.
            </span>
          </label>
        </div>
      )}
    </div>
  )
}

/** 还没被人碰过的那些问法(`origin='ai'` 只可能来自生成 Job / 灌数,见 `api/text2sql.py`)。 */
function aiCount(intent: SqlIntentDetail): number {
  return intent.questions.filter((q) => q.origin === 'ai').length
}

/** 相似问法:一行一条,一条一个索引面。保存即重建(已发布时)。 */
function QuestionsCard({ intent, onSaved }: { intent: SqlIntentDetail; onSaved: () => void }) {
  const stored = intent.questions.map((q) => q.question_text).join('\n')
  const [draft, setDraft] = useState<string | null>(null)
  const [busy, setBusy] = useState<'gen' | 'save' | null>(null)
  const [dropped, setDropped] = useState<QuestionsGenerated['dropped']>([])
  const text = draft ?? stored
  const lines = text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
  const dirty = draft !== null && draft !== stored

  const generate = async () => {
    setBusy('gen')
    try {
      const res = await apiPost<QuestionsGenerated>(
        `/api/text2sql/intents/${intent.id}/questions/generate?n=${QUESTIONS_N}`,
      )
      // 生成结果是**建议**:合进草稿等人看过再保存(避重靠 lines 里已有的那些)
      const merged = [...lines, ...res.questions.filter((q) => !lines.includes(q))]
      setDraft(merged.join('\n'))
      setDropped(res.dropped)
      pushToast(
        'success',
        `${res.questions.length} questions suggested`,
        res.dropped.length
          ? `${res.dropped.length} dropped for clashing with other intents.`
          : 'Nothing is stored yet — review, then Save.',
      )
    } catch (e) {
      pushToast('error', 'generate_failed', reason(e, 'Could not generate similar questions.'))
    } finally {
      setBusy(null)
    }
  }

  const save = async () => {
    setBusy('save')
    try {
      const res = await apiPut<QuestionsSaveResult>(
        `/api/text2sql/intents/${intent.id}/questions`,
        { questions: lines },
      )
      setDraft(null)
      onSaved()
      pushToast(
        'success',
        `${res.questions.length} questions saved`,
        res.faces
          ? `${res.faces} index faces rebuilt — retrieval already uses them.`
          : 'This intent is still a draft, so nothing is indexed yet.',
      )
    } catch (e) {
      pushToast('error', 'save_failed', reason(e, 'Could not save the questions.'))
    } finally {
      setBusy(null)
    }
  }

  return (
    <CardShell
      icon={Sparkles}
      title="Similar questions"
      dirty={dirty}
      count={`${lines.length} lines · ${intent.face_count} faces`}
      right={
        <>
          <Button size="sm" variant="secondary" disabled={busy !== null} onClick={() => void generate()}>
            {busy === 'gen' ? <Loader2 className="animate-spin" /> : <Sparkles />}
            Suggest {QUESTIONS_N}
          </Button>
          {dirty && (
            <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
              <RotateCcw /> Revert
            </Button>
          )}
          <Button size="sm" variant="primary" disabled={!dirty || busy !== null} onClick={() => void save()}>
            <Check /> Save questions
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4 px-[26px] py-[22px]">
        <label className="flex flex-col gap-2">
          <span className="text-[12.5px] font-semibold">One question per line</span>
          <Textarea
            rows={8}
            className="text-[13px] leading-[1.8]"
            value={text}
            placeholder="How much did we sell in NSW last month?"
            onChange={(e) => setDraft(e.target.value)}
          />
          <span className="text-faint text-[11.5px] leading-[1.45]">
            Each line becomes its own vector row, so each line is one more way this intent can be
            matched. Suggestions are generated from real values in the database — never invented
            customers or warehouses.
          </span>
        </label>
        {dropped.length > 0 && (
          <div className="bg-subtle rounded-[var(--radius-panel)] px-4 py-3">
            <div className="text-fainter mb-2 font-mono text-[10.5px] tracking-[0.06em] uppercase">
              dropped by the conflict filter
            </div>
            <ul className="flex flex-col gap-1.5">
              {dropped.map((d, i) => (
                <li key={i} className="text-[11.5px] leading-[1.5]">
                  <span className="text-foreground">{String(d.question ?? '')}</span>
                  <span className="text-faint"> — {String(d.reason ?? '')}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {intent.questions.length > 0 && (
          // origin 是"这条问法从哪来的",不是"谁打的字":整组替换的保存没有逐条 diff
          // (向量挂在 intent 上,不挂在问法行上),所以走过这个编辑框的一律记 human
          <div className="text-faint flex items-center gap-2 text-[11.5px]">
            <ClipboardCopy className="size-3.5 shrink-0" />
            {aiCount(intent) > 0
              ? `Stored: ${aiCount(intent)} untouched from the model, ` +
                `${intent.questions.length - aiCount(intent)} written or reviewed by hand.`
              : `Stored: all ${intent.questions.length} written or reviewed by hand — a save ` +
                `replaces the whole list, so no line stays attributed to the model.`}
          </div>
        )}
      </div>
    </CardShell>
  )
}

/** 这一页的卡片外壳:标题栏 + unsaved 标 + 右侧动作。四张卡片长一样,所以抽出来。 */
function CardShell({
  icon: Icon,
  title,
  count,
  dirty,
  right,
  children,
}: {
  icon: typeof SquareCode
  title: string
  count?: string
  dirty?: boolean
  right?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <Card className="overflow-hidden">
      <div className="flex min-h-[54px] flex-wrap items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px] py-2">
        <Icon className="text-faint size-4" />
        <span className="text-[13px] font-semibold">{title}</span>
        {count && <span className="text-faint font-mono text-[11px]">{count}</span>}
        {dirty && <Badge tone="warning">unsaved</Badge>}
        <div className="ml-auto flex items-center gap-1.5">{right}</div>
      </div>
      {children}
    </Card>
  )
}
