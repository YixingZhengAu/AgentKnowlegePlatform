/** 「重跑摄取」那张卡 —— 本页唯一的破坏性动作,所以它自己占一块地方。
 *
 * 两个决定:
 *
 * 1. **两步确认,且确认文案要说清代价**。第一下只是"上膛",第二下才真发请求;
 *    刻意**不用 `window.confirm`**:原生弹窗会卡住自动化脚本,而且它没地方摆
 *    "现在这 N 条仍然可搜"这句最要紧的话。与文档列表的删除按钮同一套手势。
 * 2. **重跑不等于停服**。新的一批要走完人工关才发布,在那之前旧切片全程 `active` ——
 *    这是后端定死的语义(`server/app/api/document.py::reingest_document`),
 *    界面必须把它讲出来,否则没人敢在演示里点这颗按钮。
 */

import { ClipboardCheck, Loader2, RefreshCw, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, apiPost } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { pushToast } from '@/lib/toast'

import { chunkFailureText } from './chunkOps'
import type { ReingestResult } from './schema'

/**
 * 重跑摄取:两步确认 + 成功后给一条通往审核台的入口。
 *
 * @param documentId 要重跑的文档 id。
 * @param liveChunks 当前仍在索引里的切片数(确认文案要用这个数)。
 * @param onSubmitted 提交成功后通知上层刷新(文档 stage 会变回 ingesting)。
 */
export function ReingestCard({
  documentId,
  liveChunks,
  onSubmitted,
}: {
  documentId: string
  liveChunks: number
  onSubmitted: () => void
}) {
  // armed = 已上膛(点过第一下),再点一下才真发请求
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)

  const run = async () => {
    setBusy(true)
    try {
      const result = await apiPost<ReingestResult>(`/api/document/documents/${documentId}/reingest`)
      setJobId(result.job_id)
      setArmed(false)
      pushToast(
        'success',
        `Ingestion job ${result.job_id}`,
        `${result.live_chunks} chunks stay searchable until the new batch is published.`,
      )
      onSubmitted()
    } catch (error) {
      const code = error instanceof ApiError ? error.code : 'reingest_failed'
      pushToast('error', code, chunkFailureText(code))
      setArmed(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="flex flex-wrap items-center gap-[18px] px-[26px] py-[22px]">
      <span className="bg-subtle flex size-10 shrink-0 items-center justify-center rounded-[var(--radius)]">
        <RefreshCw className="text-faint size-[18px]" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="font-display mb-1 text-[14px] font-bold tracking-[-0.01em]">
          Re-run ingestion
        </div>
        <p className="text-faint max-w-[560px] text-[12.5px] leading-[1.5]">
          {armed
            ? `The ${liveChunks} chunks currently live stay searchable until you publish the new ones. The re-run parses the PDF again and produces a fresh batch of chunks that you have to review before anything is replaced.`
            : 'Parses the source PDF again and produces a fresh batch of chunks for review. Only worth doing when the chunking rules or the parse quality changed.'}
        </p>
      </div>
      {jobId && !armed && (
        <Link to={`/jobs/${jobId}/review`}>
          <Button size="sm" variant="secondary">
            <ClipboardCheck />
            Open review
          </Button>
        </Link>
      )}
      {armed ? (
        <div className="flex items-center gap-1.5">
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => setArmed(false)}>
            <X />
            Cancel
          </Button>
          <Button size="sm" variant="danger" disabled={busy} onClick={() => void run()}>
            {busy ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            {busy ? 'Starting…' : 'Yes, re-run it'}
          </Button>
        </div>
      ) : (
        <Button size="sm" variant="danger" onClick={() => setArmed(true)}>
          <RefreshCw />
          Re-run ingestion
        </Button>
      )}
    </Card>
  )
}
