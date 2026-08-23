import { cn } from '@/lib/utils'

/** 分段控件(筛选 Tab):`muted` 轨道 pill,激活项是 `dark` 实心 pill + 投影(UI-STYLE §3)。
 *
 *  这里只提供外观。哪些段、点了做什么、计数从哪来,全部由调用方决定 ——
 *  它是从审核台里抽出来的样式,不携带任何行为。 */
export function Segmented({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn('bg-muted flex items-center gap-1 rounded-[var(--radius-pill)] p-1', className)}
      {...props}
    />
  )
}

export function SegmentedItem({
  active,
  label,
  count,
  className,
  ...props
}: React.ComponentProps<'button'> & { active: boolean; label: string; count?: number }) {
  return (
    <button
      className={cn(
        'flex h-8 items-center gap-[7px] rounded-[var(--radius-pill)] px-[15px] text-[13px] transition-all duration-150',
        active
          ? 'bg-dark text-dark-foreground font-semibold shadow-[var(--shadow-pill)]'
          : 'text-secondary-foreground font-medium',
        className,
      )}
      {...props}
    >
      <span className="capitalize">{label}</span>
      {count != null && (
        <span
          className={cn(
            'font-mono text-[11px] font-normal',
            active ? 'text-primary-foreground/65' : count ? 'text-faint' : 'text-ghost',
          )}
        >
          {count}
        </span>
      )}
    </button>
  )
}
