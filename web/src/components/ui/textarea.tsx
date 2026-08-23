import type { ComponentProps } from 'react'

import { cn } from '@/lib/utils'

/** 多行输入:与 Input 同一套填充/聚焦态,行高放宽(审核台要读长答案)。 */
export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return (
    <textarea
      className={cn(
        'bg-subtle focus:bg-card focus:border-ring w-full rounded-[var(--radius)] border border-transparent px-4 py-[13px] text-[14px] leading-[1.7] transition-all duration-150 outline-none focus:shadow-[var(--shadow-focus)] focus-visible:outline-none',
        className,
      )}
      {...props}
    />
  )
}
