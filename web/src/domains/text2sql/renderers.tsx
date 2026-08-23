/** `sql_intent` 的审核渲染器 —— 泛型审核台(`components/StagingReview`)的本域实例。
 *
 * 契约见 `components/staging/types.ts`。审核台负责流程,这里只回答两个问题:
 *   1. 一条候选意图在列表行里怎么一眼看懂(`IntentItemCard`)
 *   2. 怎么改(`IntentItemEditor`)—— 改的是即将被采纳成 draft 意图的那份内容
 *
 * ★ **`confidence` 在本域不是置信度**:生成 Job 的 judge 那一步把 brief 单独喂给
 * light 模型盲判"这题要不要 GROUP BY",与声明的 type 不符就把 confidence 记成 0.5
 * (出处 `services/text2sql/ingest.py::GenerateIntentsJob.step_judge`)。审核台默认按
 * confidence 升序,所以那几条会自己排到最前 —— 卡片这里要把它说成人话:
 * **"type 与盲判不符,先看这条"**,而不是一个看不懂的 0.5。
 */

import { AlertTriangle } from 'lucide-react'

import type { ItemCardProps, ItemEditorProps } from '@/components/staging/types'
import { str, strList } from '@/components/staging/types'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Segmented, SegmentedItem } from '@/components/ui/segmented'
import { Textarea } from '@/components/ui/textarea'

import { intentTypeLabel } from './schema'

/** 盲判分歧的那条 confidence(与后端那一行常量对齐:一致 1.0 / 不一致 0.5 / 判不出来 null)。 */
const JUDGE_DISAGREES = 0.5

export function IntentItemCard({ item }: ItemCardProps) {
  const p = item.payload ?? {}
  const type = str(p, 'intent_type')
  const tables = strList(p, 'tables')
  return (
    <div className="min-w-0">
      <div className="mb-px flex items-center gap-2">
        <Badge tone={type === 'stats' ? 'info' : 'navy'}>{intentTypeLabel(type)}</Badge>
        <span className="truncate text-[13.5px] leading-[1.4] font-medium [.is-sel_&]:font-semibold [.is-sel_&]:text-[var(--primary)]">
          {str(p, 'one_liner')}
        </span>
        {item.confidence === JUDGE_DISAGREES && (
          <span
            className="text-warning flex shrink-0 items-center gap-1 text-[11px]"
            title="A blind judge read the brief alone and disagreed with this type. Check it first."
          >
            <AlertTriangle className="size-3.5" strokeWidth={2} /> check type
          </span>
        )}
      </div>
      <div className="text-ghost truncate font-mono text-[11px] leading-[1.4]">
        {tables.join(' · ') || 'no table'}
      </div>
    </div>
  )
}

export function IntentItemEditor({ payload, onChange, disabled }: ItemEditorProps) {
  const type = str(payload, 'intent_type')
  const tables = strList(payload, 'tables')
  return (
    <div className="flex flex-col gap-6">
      <Field
        label="Type"
        hint="Stats means the SQL groups and aggregates; Query means it lists rows. Getting this wrong makes the SQL template unbuildable later."
      >
        <Segmented className="w-fit">
          <SegmentedItem
            active={type === 'query'}
            label="Query"
            disabled={disabled}
            onClick={() => onChange({ intent_type: 'query' })}
          />
          <SegmentedItem
            active={type === 'stats'}
            label="Stats"
            disabled={disabled}
            onClick={() => onChange({ intent_type: 'stats' })}
          />
        </Segmented>
      </Field>

      <Field label="Summary" hint="One line. It becomes an index face, so it is also how this intent gets matched.">
        <Textarea
          rows={2}
          className="text-[14.5px] leading-[1.55] font-medium"
          value={str(payload, 'one_liner')}
          disabled={disabled}
          onChange={(e) => onChange({ one_liner: e.target.value })}
        />
      </Field>

      <Field
        label="Brief"
        hint="What the SQL has to do, in business terms. This is the only thing the template generator reads."
      >
        <Textarea
          rows={5}
          className="text-[13.5px] leading-[1.7]"
          value={str(payload, 'brief')}
          disabled={disabled}
          onChange={(e) => onChange({ brief: e.target.value })}
        />
      </Field>

      <Field label="Tables" hint="Comma separated. Only tables that are enabled in the semantic layer can be used.">
        <Input
          className="font-mono text-[12.5px]"
          value={tables.join(', ')}
          disabled={disabled}
          onChange={(e) =>
            onChange({
              tables: e.target.value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
        />
      </Field>

      <Field label="Bucket" hint="Free-text grouping, shown on the intents page.">
        <Input
          value={str(payload, 'bucket')}
          disabled={disabled}
          onChange={(e) => onChange({ bucket: e.target.value })}
        />
      </Field>
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
      {hint && <span className="text-faint text-[11.5px] leading-[1.45]">{hint}</span>}
    </label>
  )
}
