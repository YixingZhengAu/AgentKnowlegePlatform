/** 审核页 —— 泛型审核台 `<StagingReview>` 的第一个实例(S0-PLAN Step 8)。
 *
 * 这一页自己几乎不做事:查一下这批待审内容是什么类型(`item_type`),
 * 从注册表取对应渲染器,交给审核台。S1/S2/S3 的审核入口都会长成这七行,
 * 差别只在注册表里多一行渲染器。
 */

import { ClipboardCheck } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { useApi } from '@/api/hooks'
import type { Job, StagingList } from '@/api/schema'
import { EmptyState } from '@/components/EmptyState'
import { JobProgress } from '@/components/JobProgress'
import { StagingReview } from '@/components/StagingReview'
import { renderersFor } from '@/components/staging/registry'
import { StatusBadge } from '@/components/StatusBadge'
import { Skeleton } from '@/components/ui/skeleton'
import { useRightPanel } from '@/layouts/AppLayout'

export function ReviewPage() {
  const { jobId = '' } = useParams()
  const job = useApi<Job>(`/api/jobs/${jobId}`)
  // 只为了知道"这批是什么类型",取一条就够 —— 渲染器按类型选,不按条目选
  const probe = useApi<StagingList>(`/api/staging?job_id=${jobId}&limit=1&sort=created_asc`)

  const renderers = renderersFor(probe.data?.items[0]?.item_type)

  useRightPanel('Job progress', <JobProgress jobId={jobId} />, [jobId, job.data?.status])

  if (!job.data || probe.loading) return <Skeleton className="h-64 w-full" />

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="font-mono text-[12px]">{job.data.job_type}</span>
        <StatusBadge status={job.data.status} />
        <span className="text-muted-foreground text-[12px]">{renderers.label} review</span>
      </div>

      {probe.data?.items.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title="No staged items"
          description="This job did not produce anything to review."
        />
      ) : (
        <StagingReview
          jobId={jobId}
          jobStatus={job.data.status}
          itemRenderer={renderers.card}
          editorRenderer={renderers.editor}
          originPanel={renderers.origin}
          onPublished={job.reload}
        />
      )}
    </div>
  )
}
