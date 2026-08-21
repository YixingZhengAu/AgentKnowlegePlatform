/** 通用任务进度条(S0-PLAN Step 7.4)—— S1/S2/S3 的摄取进度都用它,不各写一遍。
 *
 * 它只依赖 Job 框架的四个字段,与 job_type 无关:
 *   `steps`(声明式步骤骨架)/ `progress` / `step_logs` / `error`
 * 所以任务还没开始跑,骨架就已经画出来了 —— 用户看到的是"四步里第二步",
 * 而不是"日志冒了两行"。这正是把 steps 做成数据而非代码流程的收益。
 *
 * 轮询靠 `useApi(..., { refetchInterval })`:到终态就把间隔传 null,接口彻底安静。
 */

import { AlertTriangle, Check, Loader2, RotateCcw } from 'lucide-react'
import { useState } from 'react'

import { apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import { isJobActive, type Job, type JobStepDef, type JobStepLog } from '@/api/schema'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { fmtMs } from '@/lib/format'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

const POLL_MS = 1000

type StepState = 'done' | 'failed' | 'running' | 'pending'

/** 一个步骤"现在什么状态",由声明的步骤 + 已产生的日志推导,后端不用额外给字段。 */
function stepState(step: JobStepDef, job: Job, logs: JobStepLog[]): StepState {
  const mine = logs.filter((l) => l.step === step.name && l.status !== 'info')
  const last = mine[mine.length - 1]
  if (last?.status === 'ok') return 'done'
  if (last?.status === 'error' && job.status === 'failed') return 'failed'
  if (job.current_step === step.name && isJobActive(job.status)) return 'running'
  return 'pending'
}

export function JobProgress({ jobId }: { jobId: string }) {
  const [retrying, setRetrying] = useState(false)
  // 轮询到终态自动停(重跑后状态回到 queued,轮询自己就恢复了 —— 不需要额外的开关状态)
  const state = useApi<Job>(`/api/jobs/${jobId}`, {
    refetchInterval: (job) => (!job || isJobActive(job.status) ? POLL_MS : null),
  })
  const job = state.data

  if (!job) return <Skeleton className="m-5 h-32" />

  const steps = job.steps as unknown as JobStepDef[]
  const logs = job.step_logs as unknown as JobStepLog[]
  const failedStep = job.error?.step as string | undefined

  const retry = async () => {
    setRetrying(true)
    try {
      await apiPost<Job>(`/api/jobs/${jobId}/retry`)
      state.reload()
    } catch {
      // 失败的 toast 已由 apiFetch 的调用方约定:这里补一条,因为写操作不走 useApi
      pushToast('error', 'retry_failed', 'Could not restart this job.')
    } finally {
      setRetrying(false)
    }
  }

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 border-b px-5 py-3">
        <span className="font-mono text-[12px]">{job.job_type}</span>
        <StatusBadge status={job.status} />
        <span className="text-muted-foreground ml-auto font-mono text-[11px]">{job.progress}%</span>
      </div>

      {/* 进度条:navy 填充,一档过渡,不做条纹动画(UI-STYLE §3) */}
      <div className="px-5 pt-4">
        <div className="bg-muted h-1.5 w-full overflow-hidden rounded-full">
          <div
            className={cn(
              'h-full rounded-full transition-[width] duration-300',
              job.status === 'failed' ? 'bg-destructive' : 'bg-primary',
            )}
            style={{ width: `${job.progress}%` }}
          />
        </div>
      </div>

      <ol className="flex flex-col gap-0.5 px-5 py-4">
        {steps.map((step) => {
          const st = stepState(step, job, logs)
          const log = [...logs].reverse().find((l) => l.step === step.name && l.status !== 'info')
          return (
            <li key={step.name} className="flex items-start gap-2 py-1.5">
              <StepIcon state={st} />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span
                    className={cn(
                      'font-mono text-[12px]',
                      st === 'pending' && 'text-muted-foreground',
                      st === 'failed' && 'text-destructive',
                    )}
                  >
                    {step.name}
                  </span>
                  <span className="text-muted-foreground truncate text-[12px]">{step.title}</span>
                  {log?.latency_ms != null && (
                    <span className="text-muted-foreground ml-auto shrink-0 font-mono text-[11px]">
                      {fmtMs(log.latency_ms)}
                    </span>
                  )}
                </div>
                {log?.message && (
                  <p
                    className={cn(
                      'mt-0.5 font-mono text-[11px]',
                      st === 'failed' ? 'text-destructive' : 'text-muted-foreground',
                    )}
                  >
                    {log.message}
                  </p>
                )}
              </div>
            </li>
          )
        })}
      </ol>

      {job.status === 'failed' && (
        <div className="border-t px-5 py-4">
          {/* 失败原因已经在对应步骤那行显示过了,这里只说"停在哪一步" */}
          <div className="text-destructive mb-2 flex items-center gap-2 text-[12px]">
            <AlertTriangle className="size-4 shrink-0" />
            {failedStep ? `Failed at step '${failedStep}'.` : 'This job failed.'}
          </div>
          <Button variant="secondary" size="sm" onClick={retry} disabled={retrying}>
            <RotateCcw className={cn(retrying && 'animate-spin')} />
            {failedStep ? `Retry from '${failedStep}'` : 'Retry'}
          </Button>
        </div>
      )}

      {job.status === 'review' && (
        <div className="text-muted-foreground border-t px-5 py-4 text-[12px]">
          {(job.stats?.staged as number) ?? 0} items are waiting for review. The review workspace
          arrives next.
        </div>
      )}
    </div>
  )
}

function StepIcon({ state }: { state: StepState }) {
  if (state === 'done') return <Check className="text-success mt-0.5 size-4 shrink-0" />
  if (state === 'failed')
    return <AlertTriangle className="text-destructive mt-0.5 size-4 shrink-0" />
  if (state === 'running')
    return <Loader2 className="text-info mt-0.5 size-4 shrink-0 animate-spin" />
  return <span className="border-border mt-1.5 size-2 shrink-0 rounded-full border" />
}
