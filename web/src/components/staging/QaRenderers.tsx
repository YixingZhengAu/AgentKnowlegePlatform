/** 精准 QA(item_type=`qa_pair`)的渲染器 —— S1 的审核界面就是这一对 + 泛型审核台。
 *
 * payload 形状见 DB-DESIGN §8:standard_question / answer / similar_questions / keywords。
 */

import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

import {
  str,
  strList,
  type ItemCardProps,
  type ItemEditorProps,
  type OriginPanelProps,
} from './types'

export function QaItemCard({ item }: ItemCardProps) {
  const q = str(item.payload, 'standard_question')
  const a = str(item.payload, 'answer')
  return (
    <div className="min-w-0">
      <div className="truncate text-[13px] font-medium">{q || '(no question)'}</div>
      <div className="text-muted-foreground truncate text-[12px]">{a}</div>
    </div>
  )
}

export function QaItemEditor({ payload, onChange, disabled }: ItemEditorProps) {
  const similar = strList(payload, 'similar_questions')
  const keywords = strList(payload, 'keywords')
  return (
    <div className="flex flex-col gap-4">
      <Field label="Standard question">
        <Input
          value={str(payload, 'standard_question')}
          disabled={disabled}
          onChange={(e) => onChange({ standard_question: e.target.value })}
        />
      </Field>
      <Field label="Answer">
        <Textarea
          rows={6}
          value={str(payload, 'answer')}
          disabled={disabled}
          onChange={(e) => onChange({ answer: e.target.value })}
        />
      </Field>
      <Field label="Similar questions" hint="One per line">
        <Textarea
          rows={3}
          value={similar.join('\n')}
          disabled={disabled}
          // 空行不算一个相似问:审核时按回车换行是常态,不该留下空条目
          onChange={(e) =>
            onChange({ similar_questions: e.target.value.split('\n').filter((s) => s.trim()) })
          }
        />
      </Field>
      <Field label="Keywords" hint="Comma separated">
        <Input
          value={keywords.join(', ')}
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

/** 溯源面板:假任务给的是 `{page, quote}`,S2 的文档会给真的原文片段。 */
export function QaOriginPanel({ item }: OriginPanelProps) {
  const ref = (item.origin_ref ?? {}) as Record<string, unknown>
  const quote = typeof ref.quote === 'string' ? ref.quote : null
  if (!quote && ref.page == null) return null
  return (
    <div className="text-muted-foreground flex flex-col gap-1 text-[12px]">
      {ref.page != null && <span className="font-mono">page {String(ref.page)}</span>}
      {quote && <p className="border-l-2 pl-3 leading-relaxed italic">{quote}</p>}
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
    <label className="flex flex-col gap-1.5">
      <span className="flex items-baseline gap-2">
        <span className="text-secondary-foreground text-[12px] font-medium">{label}</span>
        {hint && <span className="text-muted-foreground text-[11px]">{hint}</span>}
      </span>
      {children}
    </label>
  )
}
