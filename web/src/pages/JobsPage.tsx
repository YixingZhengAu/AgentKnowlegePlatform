/** 摄取任务页 —— Job 框架的联调界面(S0-PLAN Step 7.3/7.4)。
 *
 * S0 只有一个假任务 `demo_sleep`,但这页的形状就是 S1–S3 摄取的形状:
 * 选知识库 → 提交任务 → 右侧看进度与分步日志 → 失败了从失败步骤重跑。
 *
 * `fail_at` 那个下拉框是刻意留的:演示"失败会怎样"不需要断网、不需要改代码。
 */

import { ListChecks, Play } from 'lucide-react'
import { useState } from 'react'

import { apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import { isJobActive, type Job, type JobList, type KbList } from '@/api/schema'
import { DataState } from '@/components/DataState'
import { JobProgress } from '@/components/JobProgress'
import { KbTypeTag } from '@/components/KbTypeTag'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { useRightPanel } from '@/layouts/AppLayout'
import { fmtDateTime } from '@/lib/format'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

const STEPS = ['fetch', 'parse', 'extract', 'stage']

export function JobsPage() {
  const kbs = useApi<KbList>('/api/kbs')
  const [kbId, setKbId] = useState<string>('')
  const [failAt, setFailAt] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)

  // 列表也轮询:有任务在跑时状态列会自己动,没在跑就停(和进度条同一个规则)
  const jobs = useApi<JobList>('/api/jobs?limit=20', {
    refetchInterval: (data) => (data?.items.some((j) => isJobActive(j.status)) ? 2000 : null),
  })

  const effectiveKb = kbId || kbs.data?.items[0]?.id || ''

  useRightPanel(
    'Job progress',
    selected ? (
      <JobProgress jobId={selected} />
    ) : (
      <p className="text-muted-foreground p-5 text-[12px]">
        Pick a job to watch its steps, or run a demo job.
      </p>
    ),
    [selected],
  )

  const submit = async () => {
    if (!effectiveKb) return
    setSubmitting(true)
    try {
      const job = await apiPost<Job>('/api/jobs', {
        job_type: 'demo_sleep',
        kb_id: effectiveKb,
        params: { step_seconds: 2, items: 20, ...(failAt ? { fail_at: failAt } : {}) },
      })
      setSelected(job.id)
      jobs.reload()
    } catch {
      pushToast('error', 'submit_failed', 'Could not start the job.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Run a demo job</CardTitle>
          <CardDescription>
            The demo job walks four steps with a two second pause each and writes twenty items for
            review. It exercises the same executor that document and QA ingestion will use.
          </CardDescription>
        </CardHeader>
        <div className="flex flex-wrap items-end gap-4 p-6">
          <Field label="Knowledge base">
            <select
              value={effectiveKb}
              onChange={(e) => setKbId(e.target.value)}
              className="bg-card focus:border-primary h-9 rounded-[var(--radius)] border px-2 text-[14px] outline-none"
            >
              {kbs.data?.items.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Inject a failure at">
            <select
              value={failAt}
              onChange={(e) => setFailAt(e.target.value)}
              className="bg-card focus:border-primary h-9 rounded-[var(--radius)] border px-2 text-[14px] outline-none"
            >
              <option value="">No failure</option>
              {STEPS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Button variant="accent" onClick={() => void submit()} disabled={submitting}>
            <Play />
            Run demo job
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent jobs</CardTitle>
          <CardDescription>
            Click a job to follow its steps on the right. A job that outlives its worker is marked
            failed on the next start, never left running.
          </CardDescription>
        </CardHeader>
        <DataState
          state={jobs}
          isEmpty={(d) => d.items.length === 0}
          emptyIcon={ListChecks}
          emptyTitle="No jobs yet"
          emptyDescription="Run the demo job above to see the executor work."
        >
          {(data) => (
            <Table>
              <THead>
                <TR>
                  <TH>Type</TH>
                  <TH>Knowledge base</TH>
                  <TH>Status</TH>
                  <TH>Progress</TH>
                  <TH>Started</TH>
                </TR>
              </THead>
              <tbody>
                {data.items.map((job) => {
                  const kb = kbs.data?.items.find((k) => k.id === job.kb_id)
                  return (
                    <TR
                      key={job.id}
                      onClick={() => setSelected(job.id)}
                      className={cn(
                        'cursor-pointer',
                        selected === job.id && 'bg-primary-soft hover:bg-primary-soft',
                      )}
                    >
                      <TD className="font-mono text-[12px]">{job.job_type}</TD>
                      <TD>
                        {kb ? (
                          <span className="flex items-center gap-2">
                            <KbTypeTag type={kb.type} />
                            <span className="text-[13px]">{kb.name}</span>
                          </span>
                        ) : (
                          '—'
                        )}
                      </TD>
                      <TD>
                        <StatusBadge status={job.status} />
                      </TD>
                      <TD className="font-mono text-[12px]">{job.progress}%</TD>
                      <TD className="text-muted-foreground text-[12px]">
                        {fmtDateTime(job.started_at ?? job.created_at)}
                      </TD>
                    </TR>
                  )
                })}
              </tbody>
            </Table>
          )}
        </DataState>
      </Card>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-secondary-foreground text-[12px] font-medium">{label}</span>
      {children}
    </label>
  )
}
