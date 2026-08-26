/** 调试台结果列表的一行 —— 一条命中,折叠看名次,展开看原文。
 *
 * 这一行要回答的问题只有一个:**它是怎么被找到的**。所以两条腿各占一个固定槽位,
 * 没召回它的那条腿画成虚线空片,而不是把 `rank_*` 的 null 藏进一个数字里 ——
 * "只有向量腿找到了它"是整个页面最值得看的一件事,得一眼看见。
 *
 * 🩸 **展开态要重新读一次库**:`SearchHit.content` 被接口截到 400 字
 * (出处 `app/api/document.py::search`),截口可能正好切在 `![](images/…)` 中间。
 * 所以展开时按 `chunk_id` 走 `GET /api/document/chunks/{id}` 拿全文,
 * 与引用 `[n]` 的展开态同一套做法(`Citation.tsx`);读不到就退回那 400 字。
 */

import { ChevronDown, ExternalLink, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { apiFetch } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import { ChunkContent } from './ChunkContent'
import { documentPdfUrl } from './files'
import { shortHeadingPath, type ChunkDetail, type SearchHit } from './schema'

/** 正文里的图片标记 —— 预览行要把它去掉,否则一行 `![](images/…)` 挤掉真正的字。 */
const IMAGE_MARK = /!\[[^\]]*\]\([^)]*\)/g

/** 一条命中在结果列表里的样子。
 *
 * @param hit 接口返回的这条命中。
 * @param position 最终名次(1 起),由列表下标给。
 */
export function SearchHitRow({ hit, position }: { hit: SearchHit; position: number }) {
  const [open, setOpen] = useState(false)
  const preview = hit.content.replace(IMAGE_MARK, ' ').replace(/\s+/g, ' ').trim()
  // heading_path 在这个接口里是拼好的一整串(`A > B > C`),而 shortHeadingPath 吃数组
  const heading = hit.heading_path ? shortHeadingPath(hit.heading_path.split(' > ')) : null

  return (
    <div className="border-b border-[var(--border-soft)] last:border-0">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="hover:bg-subtle flex w-full items-start gap-4 px-[26px] py-3.5 text-left transition-colors duration-150"
      >
        <span className="text-fainter mt-0.5 w-6 shrink-0 font-mono text-[11px]">#{position}</span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="max-w-[280px] truncate text-[13.5px] font-medium">{hit.doc_name}</span>
            <LegChip label="Vector" rank={hit.rank_vector} tone="info" />
            <LegChip label="Keyword" rank={hit.rank_fts} tone="navy" />
            {hit.figures > 0 && (
              <Badge tone="neutral">
                {hit.figures} {hit.figures === 1 ? 'figure' : 'figures'}
              </Badge>
            )}
          </div>
          {heading && <div className="text-faint mt-1 text-[11.5px] leading-[1.5]">{heading}</div>}
          <p className="text-faint mt-1.5 line-clamp-2 text-[12.5px] leading-[1.6]">{preview}</p>
        </div>

        <div className="shrink-0 text-right">
          <div className="font-mono text-[12px]">{hit.score.toFixed(4)}</div>
          <div className="text-fainter mt-0.5 font-mono text-[10.5px]">
            p{hit.page_idx + 1} · #{hit.seq}
          </div>
        </div>

        <ChevronDown
          className={cn(
            'text-ghost mt-0.5 size-3.5 shrink-0 transition-transform duration-150',
            !open && '-rotate-90',
          )}
        />
      </button>

      {open && <HitDetail hit={hit} />}
    </div>
  )
}

/** 一条腿的槽位:召回了画实心徽标 + 名次,没召回画虚线空片。
 *
 * 空片刻意保留同样的高度与位置,让"一条腿缺席"在一列里对得整整齐齐。
 */
function LegChip({
  label,
  rank,
  tone,
}: {
  label: string
  rank: number | null | undefined
  tone: 'info' | 'navy'
}) {
  if (rank == null) {
    return (
      <span className="text-fainter inline-flex h-[22px] items-center rounded-full border border-dashed border-[var(--border-strong)] px-2.5 text-[11.5px] font-semibold whitespace-nowrap">
        {label} — not recalled
      </span>
    )
  }
  return (
    <Badge tone={tone}>
      {label} #{rank}
    </Badge>
  )
}

/** 展开态:一句话说清是哪条腿找到的,加全文与原件 PDF 外链。 */
function HitDetail({ hit }: { hit: SearchHit }) {
  const [detail, setDetail] = useState<ChunkDetail | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true
    apiFetch<ChunkDetail>(`/api/document/chunks/${hit.chunk_id}`)
      .then((d) => alive && setDetail(d))
      .catch(() => alive && setFailed(true))
    return () => {
      alive = false
    }
  }, [hit.chunk_id])

  return (
    <div className="bg-subtle mx-[26px] mb-3.5 rounded-[var(--radius)] px-4 py-3">
      <div className="text-fainter mb-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 font-mono text-[10.5px] tracking-[0.06em] uppercase">
        <span>{hit.doc_name}</span>
        <span>page {hit.page_idx + 1}</span>
        <span>chunk #{hit.seq}</span>
        <a
          href={documentPdfUrl(hit.document_id, hit.page_idx + 1)}
          target="_blank"
          rel="noreferrer"
          className="hover:text-body ml-auto inline-flex items-center gap-1 normal-case"
        >
          <ExternalLink className="size-3" />
          Source PDF
        </a>
      </div>

      <p className="text-faint mb-2.5 text-[11.5px] leading-[1.5]">{legSentence(hit)}</p>

      {detail ? (
        <ChunkContent content={detail.content} documentId={detail.document_id} />
      ) : failed ? (
        <p className="text-[12.5px] leading-[1.7] whitespace-pre-wrap">{hit.content}</p>
      ) : (
        <span className="text-faint flex items-center gap-2 text-[12px]">
          <Loader2 className="size-3.5 animate-spin" />
          Loading the full chunk…
        </span>
      )}
    </div>
  )
}

/** 把两条腿的名次翻成一句人话 —— 数字旁边总该有句话解释它意味着什么。 */
function legSentence(hit: SearchHit): string {
  const v = hit.rank_vector
  const f = hit.rank_fts
  if (v != null && f != null) {
    return `Both legs recalled this chunk — vector at position ${v}, keyword at position ${f} — so RRF pushed it up.`
  }
  if (v != null) {
    return `Only the vector leg recalled this chunk (position ${v}); the keyword search missed it, so the wording differs from the question.`
  }
  if (f != null) {
    return `Only the keyword leg recalled this chunk (position ${f}); the embedding was not close enough, so an exact term carried it.`
  }
  return 'Neither leg reported a position for this chunk.'
}
