import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** 表头浅灰底 + 12px 大写 muted,行 hover 更浅的灰,不用斑马纹(UI-STYLE §3)。 */
export function Table({ className, ...props }: ComponentProps<'table'>) {
  return (
    <div className="w-full overflow-x-auto">
      <table className={cn('w-full border-collapse text-left', className)} {...props} />
    </div>
  )
}

export function THead({ className, ...props }: ComponentProps<'thead'>) {
  return <thead className={cn('bg-muted', className)} {...props} />
}

export function TH({ className, ...props }: ComponentProps<'th'>) {
  return (
    <th
      className={cn(
        'text-muted-foreground border-b px-4 py-2 text-[12px] font-semibold tracking-wide uppercase',
        className,
      )}
      {...props}
    />
  )
}

export function TR({ className, ...props }: ComponentProps<'tr'>) {
  return (
    <tr
      className={cn('hover:bg-subtle border-b transition-colors last:border-0', className)}
      {...props}
    />
  )
}

export function TD({ className, ...props }: ComponentProps<'td'>) {
  return <td className={cn('px-4 py-3 align-middle', className)} {...props} />
}
