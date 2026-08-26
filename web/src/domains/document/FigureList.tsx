/** 切片里的图/表清单(只读)。
 *
 * 为什么只读:`content` 里那两行 `[table description] …` / `![](images/<sha>.jpg)`
 * 才是会被检索命中的东西,改描述要改在上面的正文里;这一栏的用途是**对照** ——
 * 模型写的那句描述到底说的是不是这张图。所以它给的是图 + 描述 + 截断标记,不给输入框。
 */

import { Badge } from '@/components/ui/badge'

import { figureUrl } from './files'
import type { Figure } from './schema'

/** 渲染一条切片的全部图表。
 *
 * @param figures payload 里的 `figures[]`。
 * @param documentId 拼图片地址用(来自 `origin_ref.document_id`)。
 */
export function FigureList({ figures, documentId }: { figures: Figure[]; documentId: string }) {
  if (figures.length === 0) return null
  return (
    <div className="flex flex-col gap-3">
      <span className="text-[12.5px] font-semibold">Figures in this chunk ({figures.length})</span>
      {figures.map((figure, i) => (
        <div
          // 同一条切片里 img 可能重复(同一张图被两处引用),所以带上序号
          key={`${figure.img}-${i}`}
          className="bg-subtle flex flex-col gap-2.5 rounded-[var(--radius)] p-3.5"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="navy">{figure.kind}</Badge>
            <span className="text-faint font-mono text-[11px]">page {figure.page_idx + 1}</span>
            {figure.truncated && <Badge tone="warning">description truncated</Badge>}
          </div>

          <img
            src={figureUrl(documentId, figure.img)}
            alt={figure.description ?? `${figure.kind} on page ${figure.page_idx + 1}`}
            loading="lazy"
            className="bg-card max-h-[320px] w-full rounded-[var(--radius)] border border-[var(--border-soft)] object-contain"
          />

          <p className="text-[12.5px] leading-[1.65]">
            {figure.description ?? (
              <span className="text-ghost">No description was generated for this figure.</span>
            )}
          </p>

          {figure.source_caption.length > 0 && (
            <p className="text-faint text-[11.5px] leading-[1.5]">
              Caption: {figure.source_caption.join(' · ')}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
