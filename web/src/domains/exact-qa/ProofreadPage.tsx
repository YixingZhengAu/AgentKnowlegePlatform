/** 解析校对页 —— S1 的第一道人工关(S1-plan §4 第 3 步),也是本域最大的前端件。
 *
 * 形状:**左边原件 PDF,右边解析出来的 markdown**。校对的定义就是"对着原件看解析对不对",
 * 所以两边必须同屏;右边可切 Edit / Preview —— Edit 改的是即将喂给抽取的那份文本,
 * Preview 看的是它渲染出来什么(表格还原对不对、图片是不是真能显示)。
 *
 * 三个关键约定:
 *
 * 1. **保存写的是 `reviewed.md`,永不覆盖 `paged.md`**(后端契约)。所以页头会显示
 *    当前读的是哪一份 —— 校对过的文档再进来看到的是自己改过的版本。
 * 2. **`<!-- page: N -->` 标记不能删**:抽取靠它给候选标页码(`extractor.split_by_pages`)。
 *    编辑器里它们是可见的普通文本,所以这里加了一道"标记少了"的提示(不拦保存,只提醒)。
 * 3. **确认抽取前先落盘**:点 CTA 时如果有未保存的改动,先 PUT 再 POST ——
 *    否则人明明改了却抽的是旧文本,这种错事后极难发现。
 *
 * 从候选审核台的引用点过来时带 `?page=N&quote=...`:进来就跳到那一页,并在编辑器里
 * 把那句原文选中(bbox 高亮需要在 PDF 上画布叠加,S1 不做 —— 逐字引用的定位价值更大)。
 */

import { AlertTriangle, ArrowLeft, Eye, FileText, Pencil, Save, Sparkles } from 'lucide-react'
import { useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { apiFetch, apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import { EmptyState } from '@/components/EmptyState'
import { JobProgress } from '@/components/JobProgress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useRightPanel } from '@/layouts/rightPanel'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

import { MarkdownView } from './MarkdownView'
import { PAGE_MARKER, pageAnchor } from './pagedMd'
import type { ConfirmExtractResult, ExactQaDocument, ReviewText } from './schema'
import { STAGE_LABEL, stageTone } from './schema'

const countMarkers = (text: string) => [...text.matchAll(PAGE_MARKER)].length

export function ProofreadPage() {
  const { documentId = '' } = useParams()
  const [search] = useSearchParams()
  const navigate = useNavigate()

  const doc = useApi<ExactQaDocument>(`/api/exact-qa/documents/${documentId}`)
  const review = useApi<ReviewText>(`/api/exact-qa/documents/${documentId}/review-text`)

  const quote = search.get('quote') ?? ''
  const [draft, setDraft] = useState<string | null>(null)
  // 带着引用进来的人是来核对某一句的 —— 直接落在 Edit(能选中那句),否则默认 Preview
  const [mode, setMode] = useState<'edit' | 'preview'>(quote ? 'edit' : 'preview')
  const [page, setPage] = useState(() => Math.max(1, Number(search.get('page') ?? 1)))
  const [busy, setBusy] = useState(false)
  const editorRef = useRef<HTMLTextAreaElement | null>(null)
  // 自动定位只做一次:之后人滚到哪儿是人的事,不该被重渲染拽回去
  const jumped = useRef(false)

  const saved = review.data?.text ?? ''
  const text = draft ?? saved
  const dirty = draft !== null && draft !== saved
  const lostMarkers = countMarkers(saved) - countMarkers(text)

  useRightPanel(
    'Parse progress',
    doc.data?.parse_job_id ? <JobProgress jobId={doc.data.parse_job_id} /> : null,
    [doc.data?.parse_job_id],
  )

  /** 在编辑器里定位并选中引用原文 —— 找不到就说找不到,不假装跳成功了。 */
  const locateQuote = (el: HTMLTextAreaElement | null = editorRef.current) => {
    if (!el || !quote) return
    const at = el.value.indexOf(quote)
    if (at === -1) {
      pushToast(
        'error',
        'quote_not_found',
        'This quote is no longer in the text (it may have been edited).',
      )
      return
    }
    el.focus()
    el.setSelectionRange(at, at + quote.length)
    // textarea 没有"滚到第 N 个字符"的 API:按行比例估算滚动位置就够用了
    const before = el.value.slice(0, at).split('\n').length
    const lines = el.value.split('\n').length
    el.scrollTop = Math.max(0, (before / lines) * el.scrollHeight - el.clientHeight / 2)
  }

  /** 带引用进来时自动跳一次 —— 挂在 **ref 回调**而不是 effect 上。
   *
   *  为什么:文档与文本是两个请求,先回来的那个会让组件仍停在骨架态。
   *  写成 `useEffect([text])` 的话,文本先到时编辑器还没挂上(ref 是 null),
   *  等编辑器挂上时 text 又没变、effect 不再跑 —— 表现为"手点能跳、进页面自动跳不动"。
   *  Step 7b 的浏览器自测抓到的正是这个。 */
  const attachEditor = (el: HTMLTextAreaElement | null) => {
    editorRef.current = el
    if (el && quote && !jumped.current && el.value) {
      jumped.current = true
      locateQuote(el)
    }
  }

  const save = async (): Promise<boolean> => {
    if (!dirty) return true
    setBusy(true)
    try {
      await apiFetch<ReviewText>(`/api/exact-qa/documents/${documentId}/review-text`, {
        method: 'PUT',
        body: JSON.stringify({ text }),
      })
      setDraft(null)
      review.reload()
      pushToast('success', 'Saved to reviewed.md', 'Extraction will use this text.')
      return true
    } catch {
      pushToast('error', 'save_failed', 'Could not save the proofread text.')
      return false
    } finally {
      setBusy(false)
    }
  }

  const confirmExtract = async () => {
    // 先落盘再抽取:顺序反了就会拿旧文本去抽(见文件头约定 3)
    if (!(await save())) return
    setBusy(true)
    try {
      const res = await apiPost<ConfirmExtractResult>(
        `/api/exact-qa/documents/${documentId}/confirm-extract`,
      )
      // 直接去审核台:抽取还在跑,右侧进度面板会一步步长出来,跑完候选就出现在左边
      navigate(`/jobs/${res.job_id}/review`)
    } catch {
      pushToast('error', 'extract_failed', 'Could not start extraction.')
    } finally {
      setBusy(false)
    }
  }

  if (!doc.data || (review.loading && !review.data)) return <Skeleton className="h-64 w-full" />

  // 解析没成功就没有可校对的文本(后端 409 not_parsed)。这里不摆一个空编辑器
  // 假装能校对 —— 说清楚卡在哪,重跑入口在右侧进度面板里
  if (!review.data) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title={`Nothing to proofread yet (${doc.data.parse_status})`}
        description={
          doc.data.parse_error ??
          'The parsed text is not available. Check the parse job on the right and retry the failed step.'
        }
      />
    )
  }

  const pageCount = review.data.pages.length
  const stage = doc.data.stage

  return (
    <div className="flex h-[calc(100vh-6.5rem)] flex-col gap-3">
      {/* 页头:文档身份 + 解析统计 + 两个动作 */}
      <div className="bg-card flex flex-wrap items-center gap-3 rounded-[var(--radius-card)] border px-4 py-3 shadow-[var(--shadow-card)]">
        <Link
          to="/ingest/exact-qa"
          className="text-muted-foreground hover:text-foreground flex items-center gap-1 text-[12px]"
        >
          <ArrowLeft className="size-3.5" /> Documents
        </Link>
        <span className="font-display text-[14px] font-semibold">{doc.data.name}</span>
        <Badge tone={stageTone(stage)}>{STAGE_LABEL[stage] ?? stage}</Badge>
        {review.data && (
          <span className="text-muted-foreground font-mono text-[11px]">
            {review.data.source}
            {review.data.reviewed && ' · proofread'}
          </span>
        )}
        {doc.data.parse_stats && (
          <span className="text-muted-foreground font-mono text-[11px]">
            {doc.data.parse_stats.page_count}p · {doc.data.parse_stats.block_count} blocks ·{' '}
            {doc.data.parse_stats.table_count} tables · {doc.data.parse_stats.image_count} images
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {dirty && <Badge tone="info">unsaved</Badge>}
          <Button variant="secondary" disabled={!dirty || busy} onClick={() => void save()}>
            <Save /> Save
          </Button>
          {/* 一屏一个强调 CTA(UI-STYLE §3):这一步的出口就是"确认,开始抽取" */}
          <Button variant="accent" disabled={busy} onClick={() => void confirmExtract()}>
            <Sparkles /> Confirm &amp; extract Q&amp;A
          </Button>
        </div>
      </div>

      {lostMarkers > 0 && (
        <p className="text-destructive bg-card rounded-[var(--radius)] border px-4 py-2 text-[12px]">
          {lostMarkers} page marker(s) were removed. Extraction reads{' '}
          <code className="font-mono">&lt;!-- page: N --&gt;</code> to attribute page numbers —
          candidates after the missing marker will point at the wrong page.
        </p>
      )}

      <div className="flex min-h-0 flex-1 gap-3">
        {/* 左:原件 PDF。用浏览器原生阅读器(#page=N 跳页),不引 pdf.js */}
        <div className="bg-card flex min-w-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-card)] border shadow-[var(--shadow-card)]">
          <div className="flex items-center gap-2 border-b px-4 py-2">
            <FileText className="text-muted-foreground size-4" />
            <span className="font-mono text-[11px]">source PDF</span>
            <div className="ml-auto flex items-center gap-1">
              {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  onClick={() => {
                    setPage(n)
                    // 两侧同步:Preview 那边靠页锚点滚过去
                    document.getElementById(pageAnchor(n - 1))?.scrollIntoView({ block: 'start' })
                  }}
                  className={cn(
                    'rounded-[var(--radius)] px-2 py-0.5 font-mono text-[11px]',
                    n === page ? 'bg-primary text-primary-foreground' : 'hover:bg-subtle',
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>
          <iframe
            title="Source PDF"
            className="min-h-0 flex-1"
            src={`/api/files/documents/${documentId}/pdf#page=${page}&view=FitH`}
          />
        </div>

        {/* 右:解析文本(编辑 / 预览) */}
        <div className="bg-card flex min-w-0 flex-1 flex-col overflow-hidden rounded-[var(--radius-card)] border shadow-[var(--shadow-card)]">
          <div className="flex items-center gap-2 border-b px-4 py-2">
            <span className="font-mono text-[11px]">parsed markdown</span>
            {quote && (
              <button
                onClick={() => {
                  setMode('edit')
                  locateQuote()
                }}
                className="text-info text-[12px] hover:underline"
              >
                Find the cited sentence
              </button>
            )}
            <div className="ml-auto flex items-center gap-1">
              <Toggle active={mode === 'edit'} onClick={() => setMode('edit')} icon={Pencil}>
                Edit
              </Toggle>
              <Toggle
                active={mode === 'preview'}
                onClick={() => setMode('preview')}
                icon={Eye}
              >
                Preview
              </Toggle>
            </div>
          </div>
          {mode === 'edit' ? (
            <textarea
              ref={attachEditor}
              value={text}
              onChange={(e) => setDraft(e.target.value)}
              spellCheck={false}
              className="min-h-0 flex-1 resize-none p-4 font-mono text-[12px] leading-relaxed outline-none"
            />
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              <MarkdownView text={text} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Toggle({
  active,
  onClick,
  icon: Icon,
  children,
}: {
  active: boolean
  onClick: () => void
  icon: typeof Eye
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 rounded-[var(--radius)] px-2 py-1 text-[12px]',
        active ? 'bg-primary text-primary-foreground' : 'text-secondary-foreground hover:bg-subtle',
      )}
    >
      <Icon className="size-3.5" />
      {children}
    </button>
  )
}
