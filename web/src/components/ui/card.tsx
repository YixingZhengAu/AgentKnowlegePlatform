import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** 白底卡片:18px 圆角 + `border` 细边 + 一档极轻阴影(UI-STYLE §2)。 */
export function Card({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'bg-card rounded-[var(--radius-card)] border border-[var(--border)] shadow-[var(--shadow-card)]',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'flex flex-col gap-1 border-b border-[var(--border-soft)] px-[26px] py-4',
        className,
      )}
      {...props}
    />
  )
}

export function CardTitle({ className, ...props }: ComponentProps<'h2'>) {
  return (
    <h2
      className={cn('font-display text-[15px] font-bold tracking-[-0.01em]', className)}
      {...props}
    />
  )
}

export function CardDescription({ className, ...props }: ComponentProps<'p'>) {
  return <p className={cn('text-faint text-[12.5px]', className)} {...props} />
}

export function CardContent({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('p-[26px]', className)} {...props} />
}
