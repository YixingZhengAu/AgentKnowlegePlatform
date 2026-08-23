import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

// 徽标一律 pill,每个 tone 是一对「前景 + 浅底」,不描边(UI-STYLE §2 状态表)
const badgeVariants = cva(
  'inline-flex h-[22px] items-center gap-1.5 rounded-full px-2.5 text-[11.5px] font-semibold whitespace-nowrap',
  {
    variants: {
      tone: {
        neutral: 'bg-muted text-secondary-foreground',
        navy: 'bg-primary-soft text-primary',
        accent: 'bg-accent-soft text-accent-ink',
        success: 'bg-success-soft text-success',
        warning: 'bg-warning-soft text-warning',
        danger: 'bg-destructive-soft text-destructive-ink',
        info: 'bg-info-soft text-info',
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
