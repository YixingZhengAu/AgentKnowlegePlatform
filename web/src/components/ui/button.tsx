import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

// 全部 pill(UI-STYLE §2)。对应 UI-STYLE §3 的四类:
// primary=navy 实心 + cta 投影 / secondary=白底描边 / danger=白底红字红描边 / ghost=无底
// accent 是历史调用点(「发布」这类强调动作):新语言里**没有黄色按钮**,
// 所以它渲染成 navy CTA —— 保留名字只是为了不去动一堆调用点。
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-[var(--radius-pill)] font-semibold whitespace-nowrap transition-all duration-150 disabled:pointer-events-none disabled:border-transparent disabled:bg-muted disabled:text-fainter disabled:shadow-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary:
          'bg-primary text-primary-foreground shadow-[var(--shadow-cta)] hover:bg-primary-hover hover:shadow-[var(--shadow-cta-hover)]',
        accent:
          'bg-primary text-primary-foreground shadow-[var(--shadow-cta)] hover:bg-primary-hover hover:shadow-[var(--shadow-cta-hover)]',
        secondary:
          'bg-card text-secondary-foreground border border-border-strong hover:bg-subtle hover:text-foreground',
        danger:
          'bg-card text-destructive border border-destructive-border hover:bg-destructive-hover hover:border-destructive-border-hover',
        ghost: 'text-secondary-foreground hover:bg-hover hover:text-primary',
      },
      size: {
        sm: 'h-[34px] gap-2 px-4 text-[12.5px] [&_svg]:size-[15px]',
        md: 'h-[42px] gap-[9px] px-[22px] text-[14px] [&_svg]:size-4',
        icon: 'size-[34px] [&_svg]:size-[15px]',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

export function Button({
  className,
  variant,
  size,
  ...props
}: ComponentProps<'button'> & VariantProps<typeof buttonVariants>) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
}

export { buttonVariants }
