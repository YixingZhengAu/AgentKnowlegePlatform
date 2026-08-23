/** 答案下面的引用条 —— "这句话凭什么可信"就靠它。
 *
 * S1 只有一种引用类型(`exact_qa`):命中的是人工采纳过的问答,所以引用要说清三件事:
 * **匹配到的是哪一句问法、相似度多少、原文在第几页**。分数摆出来不是炫技 ——
 * 演示时"为什么这句被判成命中"必须当场看得见,否则阈值是一个黑盒。
 *
 * 徽标用知识类型的识别色(UI-STYLE §3:精准 QA = 黄),S2/S3 加新类型时在
 * `KB_TYPE_DOT` 里已经有色了,这里只按 `citation_type` 取。
 *
 * ★ **S3 加出来的一层**:有些引用天生不是"一句原文摘录" —— 问数命中要显示结果表格 +
 * 可展开的最终 SQL。所以 `citation_type` 可以由各域在 `module.ts` 的 `citations` 里
 * 登记自己的渲染器(与审核台渲染器同一套 manifest 模式),没登记的照旧走下面这条通路。
 * 登记表**在渲染时才查**,不在模块顶层算:那会在 DOMAINS 初始化期间被求值
 * (`domains/index.ts` 的循环依赖坑),拿到 undefined。
 */

import { ChevronDown, Quote } from 'lucide-react'
import { useState, type ComponentType } from 'react'

import { KB_TYPE_DOT, KB_TYPE_LABEL, type MessageCitation } from '@/api/schema'
import { DOMAINS } from '@/domains'
import { cn } from '@/lib/utils'

/** 引用类型 → 知识类型(S1:exact_qa 引用来自 exact_qa 知识库;S3:sql 来自 text2sql)。 */
const CITATION_KB: Record<string, string> = { exact_qa: 'exact_qa', sql: 'text2sql' }

/** 一个域给某个 `citation_type` 提供的渲染器:整条引用由它画(含展开态)。 */
export type CitationRenderer = ComponentType<{ citation: MessageCitation }>

function rendererFor(citationType: string): CitationRenderer | undefined {
  for (const d of DOMAINS) {
    const r = d.citations?.[citationType]
    if (r) return r
  }
  return undefined
}

export function Citations({ items }: { items: MessageCitation[] }) {
  const [openSeq, setOpenSeq] = useState<number | null>(null)
  if (items.length === 0) return null

  return (
    <div className="mt-3.5 flex flex-col gap-1 border-t border-[var(--border)] pt-2.5">
      {items.map((c) => {
        const Domain = rendererFor(c.citation_type)
        if (Domain) return <Domain key={c.seq} citation={c} />
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
              className="hover:bg-hover -mx-2 flex w-full items-center gap-2 rounded-[var(--radius-nav)] px-2 py-1.5 text-left transition-colors duration-150"
            >
              <span
                className={cn('size-[7px] shrink-0 rounded-full', KB_TYPE_DOT[kb] ?? 'bg-muted')}
              />
              <span className="text-fainter font-mono text-[11px]">[{c.seq}]</span>
              <span className="min-w-0 flex-1 truncate text-[12.5px]">
                {extra.matched_question ?? KB_TYPE_LABEL[kb] ?? c.citation_type}
              </span>
              {extra.score != null && (
                <span className="text-faint shrink-0 font-mono text-[11px]">
                  {extra.score.toFixed(3)}
                </span>
              )}
              {extra.page_idx != null && (
                <span className="text-faint shrink-0 font-mono text-[11px]">
                  p{extra.page_idx + 1}
                </span>
              )}
              <ChevronDown
                className={cn(
                  'text-ghost size-3.5 shrink-0 transition-transform duration-150',
                  !open && '-rotate-90',
                )}
              />
            </button>
            {open && (
              <div className="bg-subtle mt-1 rounded-[var(--radius)] px-4 py-3">
                <div className="text-fainter mb-1.5 font-mono text-[10.5px] tracking-[0.06em] uppercase">
                  {extra.is_standard_question ? 'standard question' : 'similar question'}
                  {extra.page_idx != null && ` · page ${extra.page_idx + 1}`}
                </div>
                {/* snippet 是原文逐字摘录(采纳时校验过能在解析文本里定位到) */}
                <p className="flex gap-2 text-[12.5px] leading-[1.65]">
                  <Quote className="text-ghost mt-1 size-3 shrink-0" />
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
