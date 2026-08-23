/** 本域首页:上传入口 + 文档列表 + 已发布问答库(S1-plan Step 7c)。
 *
 * 一页看完整条流水线:**进来多少 → 卡在哪一步 → 最后入库多少**。
 *
 * 三个设计决定:
 *
 * 1. **`stage` 直接用后端推导的那个字段**,前端不自己拼状态。文档表只存解析态,
 *    "待校对 / 抽取中 / 待采纳 / 已完成"是后端按关联 Job 推出来的(S1-plan §8.4)——
 *    前端再推一遍就会出现两套说法。
 * 2. **每一行只有一个动作按钮**,按 stage 给:该校对就是 Proofread,该采纳就是
 *    Review candidates。列表页最怕的是摆一排按钮让人猜点哪个。
 * 3. **删除是两步**:先点垃圾桶,那一格才变成 Delete 确认。删文档会连解析产物一起删掉,
 *    不该被一次误点做掉;有已发布问答的文档后端直接 409(出处不能删成悬空)。
 * 4. **有文档在跑才轮询**:间隔由当前数据算出来(`useApi` 的 refetchInterval 支持函数),
 *    全部到终态后接口彻底安静 —— 演示时后台不该一直有请求在滚。
 */

import { ClipboardCheck, FileUp, Files, Loader2, Pencil, RotateCcw, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { apiDelete, apiUpload } from '@/api/client'
import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { fmtDateTime } from '@/lib/format'
import { pushToast } from '@/lib/toast'

import { ItemsPanel } from './ItemsPanel'
import type { DocumentList, ExactQaDocument, UploadResult } from './schema'
import { isStageActive, STAGE_LABEL, stageTone } from './schema'

const POLL_MS = 1500

export function DocumentsPage() {
  const [uploading, setUploading] = useState(false)
  // 待确认删除的那一行(null = 没有);同一时刻只可能有一行处于确认态
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const docs = useApi<DocumentList>('/api/exact-qa/documents', {
    refetchInterval: (data) =>
      data?.items.some((d) => isStageActive(d.stage)) ? POLL_MS : null,
  })

  const upload = async (file: File) => {
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await apiUpload<UploadResult>('/api/exact-qa/documents', form)
      pushToast('success', 'Upload accepted', 'Parsing started; the list updates by itself.')
      // 解析是后台 Job:立刻刷一次让这一行出现,之后靠轮询跟状态
      docs.reload()
      return res
    } catch {
      // 后端会以 409 拒非 PDF / 空文件 / 超过 50 MB,message 已由 client 翻好
      pushToast('error', 'upload_failed', 'This file was not accepted (PDF only, max 50 MB).')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const remove = async (id: string) => {
    setDeleting(true)
    try {
      await apiDelete(`/api/exact-qa/documents/${id}`)
      pushToast('success', 'Document deleted', 'Parsed output and candidates are gone too.')
      docs.reload()
    } catch {
      // 最常见的一种:这份文档已经有采纳过的问答(409)—— 让人先去下线那几条
      pushToast(
        'error',
        'delete_failed',
        'Could not delete. If it has published Q&A, disable those items first.',
      )
    } finally {
      setDeleting(false)
      setConfirmId(null)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="-mt-1 flex items-center gap-2.5">
        <span className="bg-kb-exact-qa size-2.5 rounded-full" />
        <span className="text-faint text-[13px]">Exact Q&amp;A knowledge</span>
      </div>

      {/* 上传:一屏一个强调 CTA(UI-STYLE §3) */}
      <Card className="flex flex-wrap items-center gap-[18px] px-[26px] py-[22px]">
        <span className="bg-subtle flex size-10 shrink-0 items-center justify-center rounded-[var(--radius)]">
          <FileUp className="text-faint size-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-display mb-1 text-[14px] font-bold tracking-[-0.01em]">
            Upload a PDF
          </div>
          <p className="text-faint max-w-[520px] text-[12.5px] leading-[1.5]">
            The document is parsed, then you proofread the parsed text before any Q&amp;A is
            extracted. PDF only, up to 50 MB.
          </p>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          aria-label="PDF file"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void upload(file)
          }}
        />
        <Button variant="accent" disabled={uploading} onClick={() => fileRef.current?.click()}>
          {uploading ? <Loader2 className="animate-spin" /> : <FileUp />}
          {uploading ? 'Uploading…' : 'Choose PDF'}
        </Button>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
          <Files className="text-faint size-4" />
          <span className="text-[13px] font-semibold">Documents</span>
          <span className="text-faint ml-auto font-mono text-[11px]">
            {docs.data?.items.length ?? 0} documents
          </span>
        </div>
        <DataState
          state={docs}
          isEmpty={(d) => d.items.length === 0}
          emptyIcon={Files}
          emptyTitle="No documents yet"
          emptyDescription="Upload a PDF to start the exact Q&A pipeline."
        >
          {(data) => (
            <Table>
              <THead>
                <TR>
                  <TH>Document</TH>
                  <TH>Stage</TH>
                  <TH>Parsed</TH>
                  <TH>Candidates</TH>
                  <TH>Uploaded</TH>
                  <TH />
                </TR>
              </THead>
              <tbody>
                {data.items.map((doc) => (
                  <TR key={doc.id}>
                    <TD className="max-w-[280px]">
                      <div className="truncate text-[13.5px] font-medium">{doc.name}</div>
                      {doc.parse_error && (
                        <div className="text-destructive-ink mt-0.5 font-mono text-[10.5px]">
                          {doc.parse_error}
                        </div>
                      )}
                    </TD>
                    <TD>
                      <span className="inline-flex items-center gap-[7px]">
                        {isStageActive(doc.stage) && (
                          <Loader2 className="text-info size-3.5 animate-spin" />
                        )}
                        <Badge tone={stageTone(doc.stage)}>
                          {STAGE_LABEL[doc.stage] ?? doc.stage}
                        </Badge>
                      </span>
                    </TD>
                    <TD className="text-faint font-mono text-[11px]">
                      {doc.parse_stats
                        ? `${doc.parse_stats.page_count}p · ${doc.parse_stats.block_count} blocks`
                        : '—'}
                    </TD>
                    <TD className="font-mono text-[11px]">
                      <Funnel doc={doc} />
                    </TD>
                    <TD className="text-faint font-mono text-[11px]">
                      {fmtDateTime(doc.created_at)}
                    </TD>
                    <TD className="text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <RowAction doc={doc} />
                        {confirmId === doc.id ? (
                          <Button
                            size="sm"
                            variant="danger"
                            disabled={deleting}
                            onClick={() => void remove(doc.id)}
                          >
                            <Trash2 /> Delete
                          </Button>
                        ) : (
                          <button
                            type="button"
                            aria-label={`Delete ${doc.name}`}
                            className="text-fainter hover:bg-destructive-hover hover:text-destructive flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
                            onClick={() => setConfirmId(doc.id)}
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

      <ItemsPanel />
    </div>
  )
}

/** 漏斗:候选 → 采纳 / 不采纳。这就是"知识转化率",演示时最该被看到的数字。 */
function Funnel({ doc }: { doc: ExactQaDocument }) {
  const f = doc.funnel
  if (!f.candidates) return <span className="text-ghost">—</span>
  return (
    <span className="whitespace-nowrap">
      {f.candidates} → <span className="text-success">{f.accepted} accepted</span>
      {f.rejected > 0 && <span className="text-destructive"> · {f.rejected} rejected</span>}
      {f.pending > 0 && <span className="text-warning"> · {f.pending} pending</span>}
    </span>
  )
}

/** 一行一个动作:该干什么由 stage 决定,不摆一排按钮让人猜。 */
function RowAction({ doc }: { doc: ExactQaDocument }) {
  const proofread = `/ingest/exact-qa/documents/${doc.id}/proofread`

  if (doc.stage === 'review_text' || doc.stage === 'extract_failed') {
    return (
      <Link to={proofread}>
        <Button size="sm">
          {doc.stage === 'extract_failed' ? <RotateCcw /> : <Pencil />}
          {doc.stage === 'extract_failed' ? 'Retry extraction' : 'Proofread'}
        </Button>
      </Link>
    )
  }
  if (doc.extract_job_id && (doc.stage === 'review_qa' || doc.stage === 'done')) {
    return (
      <Link to={`/jobs/${doc.extract_job_id}/review`}>
        <Button size="sm" variant={doc.stage === 'review_qa' ? 'primary' : 'secondary'}>
          <ClipboardCheck />
          {doc.stage === 'review_qa' ? 'Review candidates' : 'Open review'}
        </Button>
      </Link>
    )
  }
  if (doc.stage === 'failed') {
    // 解析失败的重跑入口在校对页右侧的进度面板里(JobProgress 的"从失败步骤重跑")
    return (
      <Link to={proofread}>
        <Button size="sm" variant="secondary">
          <RotateCcw /> Open job
        </Button>
      </Link>
    )
  }
  return <span className="text-fainter font-mono text-[11px]">working…</span>
}
