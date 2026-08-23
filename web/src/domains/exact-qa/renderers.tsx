/** qa_pair 的审核渲染器三件套 —— 泛型审核台(`components/StagingReview`)的本域实例。
 *
 * 契约见 `components/staging/types.ts`。审核台负责流程,这三个组件只回答三个问题:
 *   1. 这条候选在 48px 列表行里怎么一眼看懂(`QaItemCard`)
 *   2. 怎么改(`QaItemEditor`)—— 采纳即发布,所以这里改的就是即将入库的内容
 *   3. 它是从原文哪儿来的(`QaOriginPanel`)—— 逐字引用 + 页码 + bbox
 *
 * **为什么原文对照这一栏不能省**:沙箱阶段实测过,表格来源的候选会出现
 * "行标签错位但数字看着对得上"(S1-plan Step 3 的坑),采纳前必须能看到原文那句话。
 */

import { ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import type { ItemCardProps, ItemEditorProps, OriginPanelProps } from '@/components/staging/types'

import { readOriginRef, readQaPayload } from './schema'

export function QaItemCard({ item }: ItemCardProps) {
  const qa = readQaPayload(item.payload)
  return (
    <div className="min-w-0">
      {/* 选中行的问题文字加重变 navy:选中态由审核台的行容器给出(`.is-sel`),
          渲染器不认识"选中"这个概念,只跟着容器变样式 */}
      <div className="mb-px truncate text-[13.5px] leading-[1.4] font-medium [.is-sel_&]:font-semibold [.is-sel_&]:text-[var(--primary)]">
        {qa.standard_question}
      </div>
      <div className="text-ghost truncate text-[11.5px] leading-[1.4]">{qa.answer}</div>
    </div>
  )
}

export function QaItemEditor({ payload, onChange, disabled }: ItemEditorProps) {
  const qa = readQaPayload(payload)
  return (
    <div className="flex flex-col gap-6">
      <Field label="Standard question">
        <Textarea
          rows={2}
          className="text-[14.5px] leading-[1.55] font-medium"
          value={qa.standard_question}
          disabled={disabled}
          onChange={(e) => onChange({ standard_question: e.target.value })}
        />
      </Field>

      <Field label="Answer" hint="Returned verbatim when this question is matched — no rewriting.">
        <Textarea
          rows={6}
          className="text-[14px] leading-[1.7]"
          value={qa.answer}
          disabled={disabled}
          onChange={(e) => onChange({ answer: e.target.value })}
        />
      </Field>

      {/* 相似问一行一条:它们每条都会变成一行向量(一个"索引面"),
          所以这里删一行就是少一个能被命中的问法 —— 用行数把这件事显式化 */}
      <Field
        label={`Similar questions (${qa.similar_questions.length})`}
        hint="One per line. Each line becomes its own vector row, so each line is one more way this answer can be matched."
      >
        <Textarea
          rows={6}
          className="text-[13.5px] leading-[1.8]"
          value={qa.similar_questions.join('\n')}
          disabled={disabled}
          onChange={(e) =>
            onChange({
              similar_questions: e.target.value
                .split('\n')
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
        />
      </Field>

      <Field label="Keywords" hint="Comma separated.">
        <Textarea
          rows={2}
          className="font-mono text-[12px] leading-[1.7]"
          value={qa.keywords.join(', ')}
          disabled={disabled}
          onChange={(e) =>
            onChange({
              keywords: e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
        />
      </Field>
    </div>
  )
}

/** 原文对照:逐字引用 + 页码(+1 才是人看的页号)+ bbox,并给一个跳回校对页的入口。 */
export function QaOriginPanel({ item }: OriginPanelProps) {
  const origin = readOriginRef(item.origin_ref)
  if (!origin) {
    return <p className="text-ghost text-[12.5px]">No source reference on this item.</p>
  }
  const page = origin.page_idx + 1
  const href =
    `/ingest/exact-qa/documents/${origin.document_id}/proofread` +
    `?page=${page}&quote=${encodeURIComponent(origin.quote.slice(0, 120))}`
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="navy">page {page}</Badge>
        {origin.bbox && (
          <span className="text-faint font-mono text-[11px]">
            bbox {origin.bbox.join(' · ')}
          </span>
        )}
        <Link
          to={href}
          className="text-info ml-auto inline-flex items-center gap-1 text-[12px] hover:underline"
        >
          <ExternalLink className="size-3.5" />
          Open in proofreading view
        </Link>
      </div>
      {/* 引用是逐字摘录(抽取时用它做过定位校验),所以这里原样显示,不做任何格式化 */}
      <blockquote className="bg-subtle border-l-primary rounded-r-[var(--radius)] border-l-[3px] px-4 py-3 text-[13px] leading-[1.7]">
        {origin.quote}
      </blockquote>
    </div>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-[12.5px] font-semibold">{label}</span>
      {children}
      {hint && <span className="text-ghost text-[11.5px] leading-[1.5]">{hint}</span>}
    </label>
  )
}
