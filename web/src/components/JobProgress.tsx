/** 通用任务进度条(S0-PLAN Step 7.4)—— S1/S2/S3 的摄取进度都用它,不各写一遍。
 *
 * 它只依赖 Job 框架的四个字段,与 job_type 无关:
 *   `steps`(声明式步骤骨架)/ `progress` / `step_logs` / `error`
 * 所以任务还没开始跑,骨架就已经画出来了 —— 用户看到的是"四步里第二步",
 * 而不是"日志冒了两行"。这正是把 steps 做成数据而非代码流程的收益。
 *
 * 轮询靠 `useApi(..., { refetchInterval })`:到终态就把间隔传 null,接口彻底安静。
 */

import { AlertTriangle, Check, ClipboardCheck, Loader2, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

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

  if (!job) return <Skeleton className="m-[26px] h-32" />

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
    <div className="flex flex-col px-[26px] pt-1 pb-[26px]">
      {/* 进度卡:整块唯一一处渐变(UI-STYLE §3),百分比用 mono 大字当主角 */}
      <div className="mb-6 rounded-[var(--radius-panel)] bg-[image:var(--gradient-progress)] px-5 py-[18px]">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-secondary-foreground font-mono text-[12px]">{job.job_type}</span>
          <span className="text-primary font-mono text-[24px] leading-none font-medium tracking-[-0.03em]">
            {job.progress}%
          </span>
        </div>
        <div className="mb-3.5">
          <StatusBadge status={job.status} />
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--primary)]/10">
          <div
            className={cn(
              'h-full rounded-full transition-[width] duration-300',
              job.status === 'failed' ? 'bg-destructive' : 'bg-primary',
            )}
            style={{ width: `${job.progress}%` }}
          />
        </div>
      </div>

      {/* 阶段列表是竖线时间轴:状态点连成一条线,读起来是"走到哪一步"而不是四行日志 */}
      <ol className="flex flex-col">
        {steps.map((step, i) => {
          const st = stepState(step, job, logs)
          const log = [...logs].reverse().find((l) => l.step === step.name && l.status !== 'info')
          const last = i === steps.length - 1
          return (
            <li key={step.name} className="flex gap-3.5">
              <div className="flex shrink-0 flex-col items-center">
                <StepIcon state={st} />
                {!last && (
                  <span
                    className={cn(
                      'my-1 w-[1.5px] flex-1',
                      st === 'done' ? 'bg-[var(--success-line)]' : 'bg-[var(--border)]',
                    )}
                  />
                )}
              </div>
              <div className={cn('min-w-0 flex-1 pt-px', !last && 'pb-[22px]')}>
                <div className="flex items-baseline gap-2">
                  <span
                    className={cn(
                      'text-[13px] font-semibold',
                      st === 'pending' && 'text-fainter',
                      st === 'failed' && 'text-destructive',
                    )}
                  >
                    {step.name}
                  </span>
                  <span className="text-faint truncate text-[12px]">{step.title}</span>
                  {log?.latency_ms != null && (
                    <span className="text-fainter ml-auto shrink-0 font-mono text-[11px]">
                      {fmtMs(log.latency_ms)}
                    </span>
                  )}
                </div>
                {log?.message && (
                  <p
                    className={cn(
                      'mt-[3px] text-[11.5px] leading-[1.5]',
                      st === 'failed' ? 'text-destructive' : 'text-ghost',
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
        <div className="mt-2 rounded-[var(--radius-panel)] border border-[var(--destructive-border)] px-5 py-4">
          {/* 失败原因已经在对应步骤那行显示过了,这里只说"停在哪一步" */}
          <div className="text-destructive mb-3 flex items-center gap-2 text-[12.5px]">
            <AlertTriangle className="size-4 shrink-0" strokeWidth={1.75} />
            {failedStep ? `Failed at step '${failedStep}'.` : 'This job failed.'}
          </div>
          <Button variant="secondary" size="sm" onClick={retry} disabled={retrying}>
            <RotateCcw className={cn(retrying && 'animate-spin')} />
            {failedStep ? `Retry from '${failedStep}'` : 'Retry'}
          </Button>
        </div>
      )}

      {/* ★ 只有真的产出过待审/已发条目才画这块:S3 的同步与 AI 描述用 published 当终态
          (它们不 staging 任何东西),没有这个条件就会出现"0 items published."
          和一个点进去是空审核台的按钮 */}
      {(job.status === 'review' || job.status === 'published') &&
        reviewCount(job) > 0 && (
        <div className="mt-2 rounded-[var(--radius-panel)] border border-[var(--border)] px-5 py-5 text-center">
          {/* 数字单独拎大:一眼是"还剩多少条要审",句子照旧一字不改 */}
          <div className="mb-1.5 font-mono text-[30px] leading-none font-medium tracking-[-0.03em]">
            {reviewCount(job)}
          </div>
          <span className="text-faint mb-4 block text-[12.5px]">
            {job.status === 'published' ? 'items published.' : 'items are waiting for review.'}
          </span>
          <Link to={`/jobs/${jobId}/review`} className="block">
            <Button variant="primary" size="sm" className="h-[38px] w-full text-[13px]">
              <ClipboardCheck />
              {job.status === 'published' ? 'Open review record' : 'Review items'}
            </Button>
          </Link>
        </div>
      )}
    </div>
  )
}

/** 这个 Job 到底产出了多少条待审/已发条目。`stats` 是各任务自己写的(`ctx.scratch["stats"]`),
 *  没写就是 0 —— 那种任务本来就不产出条目,审核台入口不该出现。 */
function reviewCount(job: Job): number {
  const stats = (job.stats ?? {}) as Record<string, unknown>
  const key = job.status === 'published' ? 'published' : 'staged'
  const v = stats[key]
  return typeof v === 'number' ? v : 0
}

/** 时间轴上的状态点:统一 22px 圆底,颜色即状态,不用文字重复说一遍。 */
function StepIcon({ state }: { state: StepState }) {
  const base = 'flex size-[22px] shrink-0 items-center justify-center rounded-full'
  if (state === 'done')
    return (
      <span className={cn(base, 'bg-success-soft')}>
        <Check className="text-success-dot size-3" strokeWidth={3} />
      </span>
    )
  if (state === 'failed')
    return (
      <span className={cn(base, 'bg-destructive-soft')}>
        <AlertTriangle className="text-destructive size-3" strokeWidth={2.25} />
      </span>
    )
  if (state === 'running')
    return (
      <span className={cn(base, 'bg-info-soft')}>
        <Loader2 className="text-info size-3 animate-spin" strokeWidth={2.5} />
      </span>
    )
  return (
    <span className={cn(base, 'bg-muted')}>
      <span className="bg-[var(--border-strong)] size-1.5 rounded-full" />
    </span>
  )
}
