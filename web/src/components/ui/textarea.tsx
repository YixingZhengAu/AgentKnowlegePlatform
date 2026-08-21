import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** 多行输入:与 Input 同一套聚焦态,行高放宽一点(审核台要读长答案)。 */
export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return (
    <textarea
      className={cn(
        'bg-card focus:border-primary w-full rounded-[var(--radius)] border px-3 py-2 text-[14px] leading-relaxed transition-colors outline-none focus:ring-2 focus:ring-[var(--primary-soft)]',
        className,
      )}
      {...props}
    />
  )
}
