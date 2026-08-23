/** 开关(enabled / sensitive)。域内自己的原子件 —— shared 层的 ui/ 里没有 switch,
 *  而治理页需要"一眼看出这一列在不在语义层里",复选框在几十行里读不出这个。 */

import { cn } from '@/lib/utils'

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
  tone = 'primary',
}: {
  checked: boolean
  onChange: (next: boolean) => void
  /** 无障碍名(界面上不显示;列表里靠列头说明它是什么) */
  label: string
  disabled?: boolean
  /** sensitive 用 danger 色:它开着代表"这列有风险",不是"这列好了" */
  tone?: 'primary' | 'danger'
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-[18px] w-[32px] shrink-0 items-center rounded-full transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-50',
        checked
          ? tone === 'danger'
            ? 'bg-destructive'
            : 'bg-primary'
          : 'bg-[var(--border-strong)]',
      )}
    >
      <span
        className={cn(
          'bg-card size-[14px] rounded-full shadow-[var(--shadow-xs)] transition-all duration-150',
          checked ? 'translate-x-[16px]' : 'translate-x-[2px]',
        )}
      />
    </button>
  )
}
