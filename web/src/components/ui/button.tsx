import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

// 四种按钮对应 UI-STYLE §3:
// primary=navy 底白字 / accent=黄底 navy 字(每页至多一个)/ secondary=白底描边 / danger=白底红字
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-[var(--radius)] font-display font-semibold whitespace-nowrap transition-colors duration-150 disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary: 'bg-primary text-primary-foreground hover:bg-primary-hover',
        accent: 'bg-accent text-accent-foreground font-bold hover:brightness-95',
        secondary: 'bg-card text-secondary-foreground border hover:bg-subtle',
        danger: 'bg-card text-destructive border border-destructive hover:bg-destructive/5',
        ghost: 'text-secondary-foreground hover:bg-subtle',
      },
      size: {
        sm: 'h-8 px-3 text-[12px]',
        md: 'h-9 px-4 text-[14px]',
        icon: 'size-9',
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
