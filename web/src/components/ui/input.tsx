import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** 36px 高、6px 圆角,聚焦 navy 边框 + 2px 外圈(UI-STYLE §3)。 */
export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        'bg-card focus:border-primary disabled:bg-muted disabled:text-muted-foreground h-9 w-full rounded-[var(--radius)] border px-3 text-[14px] transition-colors outline-none focus:ring-2 focus:ring-[var(--primary-soft)] disabled:cursor-not-allowed',
        className,
      )}
      {...props}
    />
  )
}
