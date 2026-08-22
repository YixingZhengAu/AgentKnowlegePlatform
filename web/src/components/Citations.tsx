/** 答案下面的引用条 —— "这句话凭什么可信"就靠它。
 *
 * S1 只有一种引用类型(`exact_qa`):命中的是人工采纳过的问答,所以引用要说清三件事:
 * **匹配到的是哪一句问法、相似度多少、原文在第几页**。分数摆出来不是炫技 ——
 * 演示时"为什么这句被判成命中"必须当场看得见,否则阈值是一个黑盒。
 *
 * 徽标用知识类型的识别色(UI-STYLE §3:精准 QA = 黄),S2/S3 加新类型时在
 * `KB_TYPE_DOT` 里已经有色了,这里只按 `citation_type` 取。
 */

import { ChevronDown, Quote } from 'lucide-react'
import { useState } from 'react'

import { KB_TYPE_DOT, KB_TYPE_LABEL, type MessageCitation } from '@/api/schema'
import { cn } from '@/lib/utils'

/** 引用类型 → 知识类型(S1:exact_qa 引用来自 exact_qa 知识库)。 */
const CITATION_KB: Record<string, string> = { exact_qa: 'exact_qa' }

export function Citations({ items }: { items: MessageCitation[] }) {
  const [openSeq, setOpenSeq] = useState<number | null>(null)
  if (items.length === 0) return null

  return (
    <div className="mt-3 flex flex-col gap-1.5 border-t pt-2">
      {items.map((c) => {
        const kb = CITATION_KB[c.citation_type] ?? c.citation_type
        const extra = c.extra ?? {}
        const open = openSeq === c.seq
        return (
          <div key={c.seq}>
            <button
              type="button"
              onClick={(e) => {
                // 气泡本身是"选中这条消息"的按钮,别让展开引用顺带切了选中
                e.stopPropagation()
                setOpenSeq(open ? null : c.seq)
              }}
              className="flex w-full items-center gap-2 text-left"
            >
              <span className={cn('size-2 shrink-0 rounded-full', KB_TYPE_DOT[kb] ?? 'bg-muted')} />
              <span className="text-muted-foreground font-mono text-[11px]">[{c.seq}]</span>
              <span className="min-w-0 flex-1 truncate text-[12px]">
                {extra.matched_question ?? KB_TYPE_LABEL[kb] ?? c.citation_type}
              </span>
              {extra.score != null && (
                <span className="text-muted-foreground shrink-0 font-mono text-[11px]">
                  {extra.score.toFixed(3)}
                </span>
              )}
              {extra.page_idx != null && (
                <span className="text-muted-foreground shrink-0 font-mono text-[11px]">
                  p{extra.page_idx + 1}
                </span>
              )}
              <ChevronDown
                className={cn(
                  'text-muted-foreground size-3.5 shrink-0 transition-transform',
                  !open && '-rotate-90',
                )}
              />
            </button>
            {open && (
              <div className="bg-subtle mt-1 rounded-[var(--radius)] px-3 py-2">
                <div className="text-muted-foreground mb-1 font-mono text-[10px] tracking-wide uppercase">
                  {extra.is_standard_question ? 'standard question' : 'similar question'}
                  {extra.page_idx != null && ` · page ${extra.page_idx + 1}`}
                </div>
                {/* snippet 是原文逐字摘录(采纳时校验过能在解析文本里定位到) */}
                <p className="flex gap-2 text-[12px] leading-relaxed">
                  <Quote className="text-muted-foreground mt-0.5 size-3 shrink-0" />
                  {c.snippet || '—'}
                </p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
