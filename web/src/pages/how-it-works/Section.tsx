/**
 * 说明页的排版骨架。
 *
 * **UI-STYLE §2「演示页字阶(作用域仅 /how-it-works)」的唯一落地处** ——
 * 24px 以上的 sans 字号只允许出现在本文件,其他任何组件里出现都算违规。
 * 页面组件只组合这里的元件,不自己写字号。
 */
import { ChevronDown } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** 正文里的 `**...**` → 强调。只支持这一种行内标记,不引 Markdown 渲染库 */
export function Emphasized({ text }: { text: string }) {
  return (
    <>
      {text.split('**').map((part, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="text-foreground font-semibold">
            {part}
          </strong>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  )
}

/** 一屏 = 一个论点。屏内段间距 28px,屏与屏的 88px 由页面容器给 */
export function Screen({
  id,
  children,
  className,
}: {
  id?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section id={id} className={cn('scroll-mt-20 space-y-7', className)}>
      {children}
    </section>
  )
}

/** 开场主张句(整页只用一次) */
export function ClaimHeadline({ children }: { children: ReactNode }) {
  return (
    <h1 className="font-display text-[34px] leading-[1.15] font-bold tracking-[-0.02em]">
      {children}
    </h1>
  )
}

/** 屏标题 */
export function ScreenTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="font-display text-[30px] leading-[1.2] font-bold tracking-[-0.02em]">
      {children}
    </h2>
  )
}

/** 开场主张的第二句 / 子页副标题 */
export function Lede({ text }: { text: string }) {
  return (
    <p className="text-secondary-foreground text-[19px] leading-[1.5] font-semibold">
      <Emphasized text={text} />
    </p>
  )
}

/** 段标题 */
export function SectionHeading({ children }: { children: ReactNode }) {
  return <h3 className="font-display text-[20px] leading-[1.3] font-semibold">{children}</h3>
}

/** 每屏至多一句的强调句 */
export function Emphasis({ text }: { text: string }) {
  return (
    <p className="border-accent text-foreground border-l-[3px] pl-5 text-[19px] leading-[1.5] font-semibold">
      <Emphasized text={text} />
    </p>
  )
}

/** 标注 / meta */
export function Meta({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn('text-faint text-[13px]', className)}>{children}</p>
}

/** 折叠区:折叠态 = 目录一行(标题 + 结论句摘要),点开才看细节。
 *  传 open + onToggle 则受控(总页 Expand all 需要统一开合);
 *  不传则内部自持状态(层子页等处零改动)。 */
export function CollapsibleScreen({
  id,
  title,
  summary,
  open: openProp,
  onToggle,
  children,
}: {
  id: string
  title: string
  summary: string
  open?: boolean
  onToggle?: () => void
  children: ReactNode
}) {
  const [openState, setOpenState] = useState(false)
  const controlled = openProp !== undefined
  const open = controlled ? openProp : openState
  const toggle = controlled ? onToggle : () => setOpenState((v) => !v)
  return (
    <section id={id} className="border-border-soft border-t">
      <button onClick={toggle} className="group flex w-full items-center gap-5 py-6 text-left">
        <span className="min-w-0 flex-1">
          <span className="font-display text-foreground block text-[24px] leading-[1.25] font-bold tracking-[-0.02em]">
            {title}
          </span>
          <span className="text-faint mt-1 block text-[13px]">{summary}</span>
        </span>
        <ChevronDown
          aria-hidden
          className={cn(
            'text-fainter group-hover:text-secondary-foreground size-5 shrink-0 transition-transform duration-150',
            open && 'rotate-180',
          )}
          strokeWidth={1.75}
        />
      </button>
      {open && <div className="space-y-7 pb-10">{children}</div>}
    </section>
  )
}
