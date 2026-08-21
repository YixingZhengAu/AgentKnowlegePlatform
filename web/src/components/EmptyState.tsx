import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

/** 空状态:一个线性图标 + 一句话 + 最多一个动作,不放插画(UI-STYLE §3)。 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center">
      <Icon className="text-muted-foreground size-8" strokeWidth={1.5} />
      <div className="font-display text-[16px] font-semibold">{title}</div>
      {description && (
        <p className="text-muted-foreground max-w-[420px] text-[12px]">{description}</p>
      )}
      {action}
    </div>
  )
}
