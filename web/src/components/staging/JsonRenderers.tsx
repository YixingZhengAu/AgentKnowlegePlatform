/** 兜底渲染器 —— 遇到还没写专用渲染器的 item_type(S2 的 chunk、S3 的 metric…)时用它。
 *
 * 有它的好处很实际:S2 刚把切片任务写出来、渲染器还没动手时,审核台**已经能用了**
 * (看 JSON、改 JSON、通过/驳回),不必等前端补齐才能验证后端。
 */

import { useState } from 'react'

import { Textarea } from '@/components/ui/textarea'

import type { ItemCardProps, ItemEditorProps } from './types'

export function JsonItemCard({ item }: ItemCardProps) {
  // 取前两个字符串字段当摘要:不认识结构也能给出"一眼看懂"的一行
  const preview = Object.entries(item.payload)
    .filter(([, v]) => typeof v === 'string')
    .slice(0, 2)
    .map(([, v]) => v as string)
  return (
    <div className="min-w-0">
      <div className="truncate text-[13px] font-medium">{preview[0] ?? item.item_type}</div>
      <div className="text-muted-foreground truncate text-[12px]">{preview[1] ?? ''}</div>
    </div>
  )
}

export function JsonItemEditor({ payload, onChange, disabled }: ItemEditorProps) {
  const [text, setText] = useState(() => JSON.stringify(payload, null, 2))
  const [error, setError] = useState<string | null>(null)

  // 只有解析成功才往上报:改坏的 JSON 不该被当成一次编辑
  const handle = (value: string) => {
    setText(value)
    try {
      const parsed = JSON.parse(value) as Record<string, unknown>
      setError(null)
      onChange(parsed)
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-secondary-foreground text-[12px] font-medium">
        Raw payload (no renderer for this type yet)
      </span>
      <Textarea
        rows={16}
        className="font-mono text-[12px]"
        value={text}
        disabled={disabled}
        onChange={(e) => handle(e.target.value)}
      />
      {error && <span className="text-destructive font-mono text-[11px]">{error}</span>}
    </div>
  )
}
