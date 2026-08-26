/** 本域首页:上传入口 + 文档列表。
 *
 * 一页看完整条流水线:**传进来什么 → 现在卡在哪 → 切出多少片**。
 *
 * 四个设计决定(与 S1 同一套,刻意保持一致):
 *
 * 1. **`stage` 直接用后端推导的那个字段**,前端不自己拼状态。文档表只存解析态,
 *    "切分中 / 待审 / 已发布"是后端按关联 Job 推出来的 —— 前端再推一遍就有两套说法。
 * 2. **每一行只有一个动作按钮**,按 stage 给。列表页最怕摆一排按钮让人猜点哪个。
 * 3. **删除是两步**:先点垃圾桶,那一格才变成 Delete 确认。删文档会连解析产物一起删。
 * 4. **有文档在跑才轮询**:间隔由当前数据算出来(`useApi` 的 refetchInterval 支持函数),
 *    全部到终态后接口彻底安静 —— 演示时后台不该一直有请求在滚。
 */

import { ClipboardCheck, FileUp, Files, Layers, Loader2, SearchCode, Trash2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, apiDelete, apiUpload } from '@/api/client'
import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { fmtDateTime } from '@/lib/format'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

import { useFileDrop } from './useFileDrop'
import type { DocumentList, DocumentOut, UploadResult } from './schema'
import { isStageActive, STAGE_LABEL, stageTone } from './schema'

const POLL_MS = 1500

/** 上传被拒的三种 code(出处 `server/app/api/document.py`)→ 人话。 */
const UPLOAD_FAILURE_TEXT: Record<string, string> = {
  unsupported_file_type: 'Only PDF files can be ingested.',
  empty_upload: 'That file is empty.',
  file_too_large: 'That file is larger than 50 MB.',
}

export function DocumentsPage() {
  const [uploading, setUploading] = useState(false)
  // 待确认删除的那一行(null = 没有);同一时刻只可能有一行处于确认态
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const docs = useApi<DocumentList>('/api/document/documents', {
    refetchInterval: (data) => (data?.items.some((d) => isStageActive(d.stage)) ? POLL_MS : null),
  })

  const upload = async (file: File) => {
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      await apiUpload<UploadResult>('/api/document/documents', form)
      pushToast('success', 'Upload accepted', 'Ingestion started; the list updates by itself.')
      // 切分是后台 Job:立刻刷一次让这一行出现,之后靠轮询跟状态
      docs.reload()
    } catch (error) {
      const code = error instanceof ApiError ? error.code : 'upload_failed'
      pushToast(
        'error',
        code,
        UPLOAD_FAILURE_TEXT[code] ?? 'This file was not accepted (PDF only, up to 50 MB).',
      )
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const remove = async (id: string) => {
    setDeleting(true)
    try {
      await apiDelete(`/api/document/documents/${id}`)
      pushToast('success', 'Document deleted', 'Parsed output and chunks are gone too.')
      docs.reload()
    } catch (error) {
      const code = error instanceof ApiError ? error.code : 'delete_failed'
      pushToast('error', code, 'Could not delete this document.')
    } finally {
      setDeleting(false)
      setConfirmId(null)
    }
  }

  // 拖进来的文件按 MIME 收,和 `accept` 属性、后端 ALLOWED_MIME 同一条口径
  const isPdf = (f: File) => f.type === 'application/pdf'
  const { dragging, handlers } = useFileDrop(
    isPdf,
    (file) => void upload(file),
    () =>
      pushToast(
        'error',
        'unsupported_file_type',
        'Document RAG only accepts PDF. Drop a .pdf file instead.',
      ),
  )

  return (
    <div className="flex flex-col gap-5">
      <div className="-mt-1 flex items-center gap-2.5">
        <span className="bg-kb-document size-2.5 rounded-full" />
        <span className="text-faint text-[13px]">Document RAG knowledge</span>
      </div>

      {/* 上传:一屏一个强调 CTA(UI-STYLE §3) */}
      <Card
        {...handlers}
        aria-label="Upload a PDF — you can also drop a file here"
        className={cn(
          'flex flex-wrap items-center gap-[18px] px-[26px] py-[22px] transition-colors duration-150',
          // 拖进来时整张卡变成投放区:边框与底色同时变,只改一个太容易看漏
          dragging && 'border-[var(--selected-border)] bg-selected',
        )}
      >
        <span className="bg-subtle flex size-10 shrink-0 items-center justify-center rounded-[var(--radius)]">
          <FileUp className="text-faint size-[18px]" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-display mb-1 text-[14px] font-bold tracking-[-0.01em]">
            Upload a PDF
          </div>
          <p className="text-faint max-w-[520px] text-[12.5px] leading-[1.5]">
            The document is parsed, cleaned and split into chunks; figures get a written
            description. You review the chunks before anything is published. PDF only, up to 50 MB.
          </p>
          <p className="text-ghost mt-1 text-[12px] leading-[1.5]">
            {dragging
              ? 'Drop the PDF to start ingesting it.'
              : 'Drag a PDF onto this card, or pick one below.'}
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
        <Link to="/ingest/document/search">
          <Button variant="secondary">
            <SearchCode />
            Retrieval console
          </Button>
        </Link>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
          <Files className="text-faint size-4" />
          <span className="text-[13px] font-semibold">Documents</span>
          <span className="text-faint ml-auto font-mono text-[11px]">
            {docs.data?.total ?? 0} documents
          </span>
        </div>
        <DataState
          state={docs}
          isEmpty={(d) => d.items.length === 0}
          emptyIcon={Files}
          emptyTitle="No documents yet"
          emptyDescription="Upload a PDF to start the document RAG pipeline."
        >
          {(data) => (
            <Table>
              <THead>
                <TR>
                  <TH>Document</TH>
                  <TH>Pages</TH>
                  <TH>Chunks</TH>
                  <TH>Stage</TH>
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
                    <TD className="text-faint font-mono text-[11px]">{doc.page_count ?? '—'}</TD>
                    <TD className="font-mono text-[11px]">
                      {doc.chunk_count > 0 ? (
                        doc.chunk_count
                      ) : (
                        <span className="text-ghost">—</span>
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
    </div>
  )
}

/** 一行一个动作:该干什么由 stage 决定,不摆一排按钮让人猜。
 *
 * 解析失败那一行不给按钮 —— 失败原因已经印在文件名底下,重跑入口在共享的 Job 面板里。
 */
function RowAction({ doc }: { doc: DocumentOut }) {
  if (doc.ingest_job_id && (doc.stage === 'review' || doc.stage === 'published')) {
    return (
      <div className="flex items-center gap-2">
        {/* 🩸 两个入口通向两张不同的表:review 看 `staging_items`(发布前的候选),
            chunks 看 `chunks`(发布后的正式行)。动作也不同:不采纳 ≠ 禁用 */}
        {doc.stage === 'published' && (
          <Link to={`/ingest/document/documents/${doc.id}/chunks`}>
            <Button size="sm" variant="primary">
              <Layers />
              Manage chunks
            </Button>
          </Link>
        )}
        <Link to={`/jobs/${doc.ingest_job_id}/review`}>
          <Button size="sm" variant={doc.stage === 'review' ? 'primary' : 'secondary'}>
            <ClipboardCheck />
            {doc.stage === 'review' ? 'Review chunks' : 'Open review'}
          </Button>
        </Link>
      </div>
    )
  }
  if (doc.stage === 'failed') return null
  return <span className="text-fainter font-mono text-[11px]">working…</span>
}
