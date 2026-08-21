import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

// 徽标是唯一允许全圆(pill)的元素(UI-STYLE §2)
const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium whitespace-nowrap',
  {
    variants: {
      tone: {
        neutral: 'bg-muted text-muted-foreground border',
        navy: 'bg-primary-soft text-primary',
        accent: 'bg-accent text-accent-foreground',
        success: 'bg-success/10 text-success',
        danger: 'bg-destructive/10 text-destructive',
        info: 'bg-info/10 text-info',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

export function Badge({
  className,
  tone,
  ...props
}: ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />
}
