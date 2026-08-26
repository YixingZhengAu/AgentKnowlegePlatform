/** 答案里那条 `[n]` 引用 —— 点开要给**全量原文 + 元数据**(分册 3 §6)。
 *
 * 与共享的通用引用条(`components/Citations.tsx` 的兜底通路)差在展开态:
 * 通用条只显示 240 字摘录,而文档 RAG 的一条切片可能是整张表格的描述,
 * 摘录里看不到"模型到底站在哪句话上"。
 *
 * 🩸 **全文不存在引用里,展开时才按 `ref_id` 实时读库**(`GET /api/document/chunks/{id}`)。
 * 于是历史会话点开看到的是切片的**当前**内容,不是提问那天的快照;
 * 代价是多一次请求,收益是不用在 `message_citations` 里存一份会漂移的副本。
 * 这样安全的前提是被引用过的切片不物理删(下线是软标志,归 S2-4)。
 */

import { ChevronDown, ExternalLink, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { apiFetch, ApiError } from '@/api/client'
import type { MessageCitation } from '@/api/schema'
import { cn } from '@/lib/utils'

import { ChunkContent } from './ChunkContent'
import { documentPdfUrl } from './files'
import { FigureList } from './FigureList'
import { readFigure, type ChunkDetail, type Figure } from './schema'

/** 一条 chunk 引用。整条由本域画(含展开态),登记在 `module.ts` 的 `citations`。 */
export function ChunkCitation({ citation }: { citation: MessageCitation }) {
  const [open, setOpen] = useState(false)
  const extra = citation.extra ?? {}
  const heading = typeof extra.heading_path === 'string' ? extra.heading_path : null
  const docName = typeof extra.document_name === 'string' ? extra.document_name : 'Document'
  const page = typeof extra.page_idx === 'number' ? extra.page_idx + 1 : null

  return (
    <div>
      <button
        type="button"
        onClick={(e) => {
          // 气泡本身是"选中这条消息"的按钮,别让展开引用顺带切了选中
          e.stopPropagation()
          setOpen(!open)
        }}
        className="hover:bg-hover -mx-2 flex w-full items-center gap-2 rounded-[var(--radius-nav)] px-2 py-1.5 text-left transition-colors duration-150"
      >
        <span className="bg-kb-document size-[7px] shrink-0 rounded-full" />
        <span className="text-fainter font-mono text-[11px]">[{citation.seq}]</span>
        <span className="min-w-0 flex-1 truncate text-[12.5px]">{heading ?? docName}</span>
        {typeof extra.score === 'number' && (
          <span className="text-faint shrink-0 font-mono text-[11px]">
            {extra.score.toFixed(3)}
          </span>
        )}
        {page != null && (
          <span className="text-faint shrink-0 font-mono text-[11px]">p{page}</span>
        )}
        <ChevronDown
          className={cn(
            'text-ghost size-3.5 shrink-0 transition-transform duration-150',
            !open && '-rotate-90',
          )}
        />
      </button>
      {open && <ChunkDetailPanel citation={citation} fallbackSnippet={citation.snippet ?? null} />}
    </div>
  )
}

/** 展开态:实时读回切片全文,读不到就退回引用里存的那段摘录。 */
function ChunkDetailPanel({
  citation,
  fallbackSnippet,
}: {
  citation: MessageCitation
  fallbackSnippet: string | null
}) {
  const [detail, setDetail] = useState<ChunkDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    apiFetch<ChunkDetail>(`/api/document/chunks/${citation.ref_id}`)
      .then((d) => alive && setDetail(d))
      .catch((e: unknown) =>
        alive
          ? setError(
              e instanceof ApiError && e.code === 'chunk_not_found'
                ? 'This chunk is no longer in the knowledge base.'
                : 'Could not load the full text of this chunk.',
            )
          : undefined,
      )
    return () => {
      alive = false
    }
  }, [citation.ref_id])

  if (error) {
    return (
      <Shell>
        <p className="text-faint text-[12px]">{error}</p>
        {fallbackSnippet && (
          <p className="mt-2 text-[12.5px] leading-[1.65]">{fallbackSnippet}</p>
        )}
      </Shell>
    )
  }

  if (!detail) {
    return (
      <Shell>
        <span className="text-faint flex items-center gap-2 text-[12px]">
          <Loader2 className="size-3.5 animate-spin" />
          Loading the full chunk…
        </span>
      </Shell>
    )
  }

  const figures = (detail.figures ?? [])
    .map(readFigure)
    .filter((f): f is Figure => f !== null)

  return (
    <Shell>
      <div className="text-fainter mb-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 font-mono text-[10.5px] tracking-[0.06em] uppercase">
        <span>{detail.document_name}</span>
        {detail.page_idx != null && <span>page {detail.page_idx + 1}</span>}
        <span>chunk #{detail.seq}</span>
        {detail.token_count != null && <span>{detail.token_count} tok</span>}
        <a
          href={documentPdfUrl(detail.document_id, (detail.page_idx ?? 0) + 1)}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="hover:text-body ml-auto inline-flex items-center gap-1 normal-case"
        >
          <ExternalLink className="size-3" />
          Source PDF
        </a>
      </div>
      {detail.heading_path && (
        <div className="text-faint mb-2 text-[11.5px] leading-[1.5]">{detail.heading_path}</div>
      )}

      <ChunkContent content={detail.content} documentId={detail.document_id} />

      {figures.length > 0 && (
        <div className="mt-4 border-t border-[var(--border-soft)] pt-3.5">
          <FigureList figures={figures} documentId={detail.document_id} />
        </div>
      )}
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="bg-subtle mt-1 rounded-[var(--radius)] px-4 py-3">{children}</div>
}
