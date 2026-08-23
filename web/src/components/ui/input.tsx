import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** 填充式输入:静息是 `subtle` 填充块 + 透明边,聚焦才变白底 + ring 边 + 4px 外圈(UI-STYLE §3)。 */
export function Input({ className, ...props }: ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        'bg-subtle focus:bg-card focus:border-ring disabled:text-fainter h-9 w-full rounded-[var(--radius)] border border-transparent px-4 text-[14px] transition-all duration-150 outline-none focus:shadow-[var(--shadow-focus)] focus-visible:outline-none disabled:cursor-not-allowed',
        className,
      )}
      {...props}
    />
  )
}
