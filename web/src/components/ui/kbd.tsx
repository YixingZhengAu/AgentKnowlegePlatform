import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** 快捷键片:mono 10.5px + 极浅底 + 5px 圆角(UI-STYLE §3)。
 *  纯展示元素,不带任何键盘监听 —— 监听在各页面自己那里。 */
export function Kbd({ className, ...props }: ComponentProps<'kbd'>) {
  return (
    <kbd
      className={cn(
        'text-muted-foreground rounded-[var(--radius-kbd)] border border-[var(--brand-line-kbd)] bg-[var(--brand-kbd)] px-[5px] py-px font-mono text-[10.5px] font-normal',
        className,
      )}
      {...props}
    />
  )
}
