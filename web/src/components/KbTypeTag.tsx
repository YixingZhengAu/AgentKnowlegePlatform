import { KB_TYPE_DOT, KB_TYPE_LABEL } from '@/api/schema'
import { cn } from '@/lib/utils'

/** 三类知识的识别标 —— 色点 + 英文标签,全站(KB 列表 / 路由徽标 / 引用标记)复用。 */
export function KbTypeTag({ type, className }: { type: string; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2 whitespace-nowrap', className)}>
      <span className={cn('size-2 rounded-full', KB_TYPE_DOT[type] ?? 'bg-muted-foreground')} />
      <span>{KB_TYPE_LABEL[type] ?? type}</span>
    </span>
  )
}
