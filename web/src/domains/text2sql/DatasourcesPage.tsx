/** D1 数据源管理页 —— 本域首页。
 *
 * 一页回答三个问题:**接了哪些库 / 连不连得上 / 治理到什么程度**。
 *
 * 四个设计决定:
 *
 * 1. **先测再存**:表单里的 Test connection 打的是 `POST /datasources/test`(不落库的那个),
 *    所以填错口令不会先在库里留下一个连不上的数据源。连不上是 200 + `ok=false` ——
 *    前端只读 `ok` 与 `error`,不解析错误码。
 * 2. **口令只在这张表单里出现一次**:存完就再也拿不回来(后端只回 host/port/user/database),
 *    所以编辑时留空 = 不改口令,而不是把口令清空。
 * 3. **Read-only confirmed 是闸不是提示**:没确认的数据源,同步 / AI 描述 / 试跑全部被后端 409。
 *    所以那一行显示的不是一个说明文字,而是一个**必须点掉的动作**。
 * 4. **同步进度用共享的 `<JobProgress>`**:治理进度那几个数字在 Job 跑的时候会自己变
 *    (列表在有 Job 时才轮询),跑完轮询停下 —— 演示时后台不该一直有请求在滚。
 */

import {
  Check,
  Database,
  ListTree,
  Loader2,
  Plug,
  Plus,
  RefreshCw,
  ShieldCheck,
  Table2,
  Trash2,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { apiDelete, apiPatch, apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
import { JobProgress } from '@/components/JobProgress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { fmtDateTime } from '@/lib/format'
import { pushToast } from '@/lib/toast'

import { reason } from './http'
import {
  connTarget,
  type ConnIn,
  type Datasource,
  type DatasourceList,
  type JobStarted,
  type TestConnectionResult,
} from './schema'
import { Toggle } from './Toggle'

const POLL_MS = 2000

export function DatasourcesPage() {
  const [adding, setAdding] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<string | null>(null)

  // 有 Job 在跑才轮询:治理进度的数字会跟着 Job 一格格变,跑完(卡片被关掉)彻底安静
  const list = useApi<DatasourceList>('/api/text2sql/datasources', {
    refetchInterval: () => (jobId ? POLL_MS : null),
  })

  const sync = async (ds: Datasource) => {
    setBusyId(ds.id)
    try {
      const job = await apiPost<JobStarted>(`/api/text2sql/datasources/${ds.id}/sync`)
      setJobId(job.job_id)
      pushToast('success', 'Sync started', 'Physical facts only — your descriptions are kept.')
    } catch (e) {
      pushToast('error', 'sync_failed', reason(e, 'Could not start the schema sync.'))
    } finally {
      setBusyId(null)
    }
  }

  const confirmReadonly = async (ds: Datasource) => {
    setBusyId(ds.id)
    try {
      await apiPatch<Datasource>(`/api/text2sql/datasources/${ds.id}`, {
        readonly_confirmed: true,
      })
      pushToast('success', 'Marked read-only', 'Sync, AI describe and Run are unlocked.')
      list.reload()
    } catch (e) {
      pushToast('error', 'update_failed', reason(e, 'Could not update this datasource.'))
    } finally {
      setBusyId(null)
    }
  }

  const remove = async (ds: Datasource) => {
    setBusyId(ds.id)
    try {
      await apiDelete(`/api/text2sql/datasources/${ds.id}`)
      pushToast('success', 'Datasource deleted', 'Its schema metadata is gone too.')
      list.reload()
    } catch (e) {
      // 最常见的一种:上面还挂着意图(409)—— 先去把那些意图删掉/下线
      pushToast('error', 'delete_failed', reason(e, 'Could not delete this datasource.'))
    } finally {
      setBusyId(null)
      setConfirmId(null)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="-mt-1 flex items-center gap-2.5">
        <span className="bg-kb-text2sql size-2.5 rounded-full" />
        <span className="text-faint text-[13px]">Structured data knowledge</span>
        {/* 治理完 schema 的下一步就在那一页(意图 + 模板);它是 kb 级的,不挂在某个数据源下 */}
        <Link to="/ingest/text2sql/intents" className="ml-auto">
          <Button size="sm" variant="secondary">
            <ListTree /> Question intents
          </Button>
        </Link>
      </div>

      {adding ? (
        <NewDatasourceCard
          onCancel={() => setAdding(false)}
          onCreated={() => {
            setAdding(false)
            list.reload()
          }}
        />
      ) : (
        <Card className="flex flex-wrap items-center gap-[18px] px-[26px] py-[22px]">
          <span className="bg-subtle flex size-10 shrink-0 items-center justify-center rounded-[var(--radius)]">
            <Plug className="text-faint size-[18px]" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="font-display mb-1 text-[14px] font-bold tracking-[-0.01em]">
              Connect a database
            </div>
            <p className="text-faint max-w-[560px] text-[12.5px] leading-[1.5]">
              MySQL, read-only account. The connection string is encrypted before it is stored and
              is never returned by the API.
            </p>
          </div>
          <Button variant="accent" onClick={() => setAdding(true)}>
            <Plus /> Add datasource
          </Button>
        </Card>
      )}

      {jobId && (
        <Card className="overflow-hidden">
          <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
            <RefreshCw className="text-faint size-4" />
            <span className="text-[13px] font-semibold">Schema sync</span>
            <button
              type="button"
              aria-label="Hide sync progress"
              className="text-fainter hover:bg-hover hover:text-foreground ml-auto flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
              onClick={() => {
                setJobId(null)
                list.reload()
              }}
            >
              <X className="size-3.5" />
            </button>
          </div>
          <JobProgress jobId={jobId} />
        </Card>
      )}

      <Card className="overflow-hidden">
        <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
          <Database className="text-faint size-4" />
          <span className="text-[13px] font-semibold">Datasources</span>
          <span className="text-faint ml-auto font-mono text-[11px]">
            {list.data?.items.length ?? 0} connected
          </span>
        </div>
        <DataState
          state={list}
          isEmpty={(d) => d.items.length === 0}
          emptyIcon={Database}
          emptyTitle="No datasource yet"
          emptyDescription="Connect a read-only MySQL account to start governing its schema."
        >
          {(data) => (
            <Table>
              <THead>
                <TR>
                  <TH>Datasource</TH>
                  <TH>Read-only</TH>
                  <TH>Governance</TH>
                  <TH>Intents</TH>
                  <TH>Last synced</TH>
                  <TH />
                </TR>
              </THead>
              <tbody>
                {data.items.map((ds) => (
                  <TR key={ds.id}>
                    <TD className="max-w-[300px]">
                      <div className="truncate text-[13.5px] font-medium">{ds.name}</div>
                      <div className="text-faint mt-0.5 truncate font-mono text-[10.5px]">
                        {ds.db_type} · {connTarget(ds)}
                      </div>
                    </TD>
                    <TD>
                      {ds.readonly_confirmed ? (
                        <Badge tone="success">
                          <ShieldCheck className="size-3" /> confirmed
                        </Badge>
                      ) : (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={busyId === ds.id}
                          onClick={() => void confirmReadonly(ds)}
                        >
                          <ShieldCheck /> Confirm
                        </Button>
                      )}
                    </TD>
                    <TD className="font-mono text-[11px] whitespace-nowrap">
                      {ds.tables === 0 ? (
                        <span className="text-ghost">not synced</span>
                      ) : (
                        <>
                          {ds.tables} tables ·{' '}
                          <span className="text-success">{ds.enabled_tables} on</span> ·{' '}
                          <span
                            className={
                              ds.described_tables < ds.enabled_tables ? 'text-warning' : ''
                            }
                          >
                            {ds.described_tables} described
                          </span>
                        </>
                      )}
                    </TD>
                    <TD className="font-mono text-[11px]">
                      {ds.published_intents ? (
                        <span className="text-primary">{ds.published_intents} published</span>
                      ) : (
                        <span className="text-ghost">0</span>
                      )}
                    </TD>
                    <TD className="text-faint font-mono text-[11px] whitespace-nowrap">
                      {ds.last_synced_at ? fmtDateTime(ds.last_synced_at) : '—'}
                    </TD>
                    <TD className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={busyId === ds.id}
                          onClick={() => void sync(ds)}
                        >
                          {busyId === ds.id ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                          {ds.tables === 0 ? 'Sync schema' : 'Re-sync'}
                        </Button>
                        <Link to={`/ingest/text2sql/datasources/${ds.id}/schema`}>
                          <Button size="sm" variant={ds.tables === 0 ? 'secondary' : 'primary'}>
                            <Table2 /> Govern schema
                          </Button>
                        </Link>
                        {confirmId === ds.id ? (
                          <Button
                            size="sm"
                            variant="danger"
                            disabled={busyId === ds.id}
                            onClick={() => void remove(ds)}
                          >
                            <Trash2 /> Delete
                          </Button>
                        ) : (
                          <button
                            type="button"
                            aria-label={`Delete ${ds.name}`}
                            className="text-fainter hover:bg-destructive-hover hover:text-destructive flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
                            onClick={() => setConfirmId(ds.id)}
                          >
                            <Trash2 className="size-3.5" />
                          </button>
                        )}
                      </div>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </DataState>
      </Card>
    </div>
  )
}

const EMPTY_CONN: ConnIn = {
  host: '127.0.0.1',
  port: 3306,
  database: '',
  user: '',
  password: '',
}

/** 新建表单。**这是全项目唯一一个收数据库口令的地方**(后端同理:唯一入参处)。 */
function NewDatasourceCard({
  onCancel,
  onCreated,
}: {
  onCancel: () => void
  onCreated: () => void
}) {
  const [name, setName] = useState('')
  const [conn, setConn] = useState<ConnIn>(EMPTY_CONN)
  const [readonly, setReadonly] = useState(true)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [tested, setTested] = useState<TestConnectionResult | null>(null)

  const set = (patch: Partial<ConnIn>) => {
    setConn((c) => ({ ...c, ...patch }))
    setTested(null) // 改了要素,上一次的测连结果就作废了
  }
  const filled = Boolean(conn.host && conn.database && conn.user)

  const test = async () => {
    setTesting(true)
    try {
      setTested(await apiPost<TestConnectionResult>('/api/text2sql/datasources/test', conn))
    } catch (e) {
      // 连不上走的是 200 + ok=false;走到这里说明请求本身出了问题
      pushToast('error', 'test_failed', reason(e, 'Could not run the connection test.'))
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      await apiPost<Datasource>('/api/text2sql/datasources', {
        name,
        conn,
        readonly_confirmed: readonly,
      })
      pushToast('success', 'Datasource saved', 'Sync its schema to start governing it.')
      onCreated()
    } catch (e) {
      pushToast('error', 'create_failed', reason(e, 'Could not save this datasource.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
        <Plug className="text-faint size-4" />
        <span className="text-[13px] font-semibold">New datasource</span>
        <button
          type="button"
          aria-label="Cancel"
          className="text-fainter hover:bg-hover hover:text-foreground ml-auto flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
          onClick={onCancel}
        >
          <X className="size-3.5" />
        </button>
      </div>
      <div className="flex flex-col gap-6 p-[26px]">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Name" hint="Shown in the datasource list.">
            <Input
              value={name}
              placeholder="Clenergy Sales (MySQL)"
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="Host">
            <Input value={conn.host} onChange={(e) => set({ host: e.target.value })} />
          </Field>
          <Field label="Port">
            <Input
              value={String(conn.port)}
              inputMode="numeric"
              className="font-mono"
              onChange={(e) => set({ port: Number(e.target.value.replace(/\D/g, '')) || 0 })}
            />
          </Field>
          <Field label="Database">
            <Input value={conn.database} onChange={(e) => set({ database: e.target.value })} />
          </Field>
          <Field label="User" hint="A read-only account: SELECT and nothing else.">
            <Input value={conn.user} onChange={(e) => set({ user: e.target.value })} />
          </Field>
          <Field label="Password" hint="Encrypted on save; never returned by the API.">
            <Input
              type="password"
              value={conn.password ?? ''}
              autoComplete="new-password"
              onChange={(e) => set({ password: e.target.value })}
            />
          </Field>
        </div>

        {/* 只读确认是闸:没勾上,后端会拒掉同步 / AI 描述 / 试跑 */}
        <label className="bg-subtle flex cursor-pointer items-start gap-3 rounded-[var(--radius-panel)] px-4 py-3.5">
          <span className="pt-0.5">
            <Toggle checked={readonly} onChange={setReadonly} label="This account is read-only" />
          </span>
          <span className="min-w-0">
            <span className="block text-[12.5px] font-semibold">This account is read-only</span>
            <span className="text-faint block text-[11.5px] leading-[1.5]">
              Until this is confirmed, schema sync, AI describe and Run are refused. Confirm it only
              after checking the account has SELECT privileges alone.
            </span>
          </span>
        </label>

        {tested && <TestResult result={tested} />}

        <div className="flex items-center gap-2.5">
          <Button variant="secondary" disabled={!filled || testing} onClick={() => void test()}>
            {testing ? <Loader2 className="animate-spin" /> : <Plug />}
            Test connection
          </Button>
          <Button
            variant="accent"
            disabled={!name || !filled || saving}
            onClick={() => void save()}
          >
            {saving ? <Loader2 className="animate-spin" /> : <Check />}
            Save datasource
          </Button>
        </div>
      </div>
    </Card>
  )
}

/** 测连结果:成功给"连上了什么"的事实(版本 + 表数),失败原样显示后端那句话。 */
function TestResult({ result }: { result: TestConnectionResult }) {
  if (!result.ok) {
    return (
      <div className="border-destructive-border rounded-[var(--radius-panel)] border px-4 py-3.5">
        <div className="text-destructive mb-1 flex items-center gap-2 text-[12.5px] font-semibold">
          <X className="size-4" strokeWidth={2.25} /> Cannot connect
        </div>
        <p className="text-destructive-ink font-mono text-[11px] leading-[1.6] break-all">
          {result.error}
        </p>
      </div>
    )
  }
  return (
    <div className="bg-success-soft rounded-[var(--radius-panel)] px-4 py-3.5">
      <div className="text-success mb-1 flex items-center gap-2 text-[12.5px] font-semibold">
        <Check className="size-4" strokeWidth={2.25} /> Connected
      </div>
      <p className="text-success font-mono text-[11px]">
        {result.target} · server {result.server_version ?? '?'} · {result.table_count ?? 0} tables
      </p>
    </div>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  // label 包住输入框(而不是靠 htmlFor 配 id):无障碍名自动绑上,也少一处要维护的 id
  return (
    <label className="flex flex-col gap-2">
      <span className="text-[12.5px] font-semibold">{label}</span>
      {children}
      {hint && <span className="text-faint text-[11.5px] leading-[1.4]">{hint}</span>}
    </label>
  )
}
