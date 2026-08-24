/**
 * `/how-it-works/:layer` 子页:一层一页,关键词卡片(不是文章)。
 * 结构:主角句 → 示例 chips → 四张卡(业务介入那张高亮)→ may / may not 两列 → 刻意不做。
 * 未知 slug 重定向回总页。
 */
import { ArrowLeft, Check, X } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'

import { BACK_TO_OVERVIEW, LAYER_DETAILS, LAYERS, type LayerSlug } from './content'
import { Emphasized, Lede, Screen, ScreenTitle, SectionHeading } from './Section'

function KeywordCard({
  heading,
  bullets,
  highlight,
}: {
  heading: string
  bullets: string[]
  highlight?: boolean
}) {
  return (
    <div
      className={
        highlight
          ? 'border-accent bg-subtle rounded-[16px] border-l-[3px] px-5 py-5'
          : 'bg-subtle rounded-[16px] px-5 py-5'
      }
    >
      <p className="font-display text-foreground text-[16px] font-semibold">{heading}</p>
      <ul className="mt-3 space-y-2">
        {bullets.map((b) => (
          <li key={b} className="text-secondary-foreground flex gap-2.5 text-[14px] leading-[1.55]">
            <span
              aria-hidden
              className="bg-border-strong mt-[8px] size-[4px] shrink-0 rounded-full"
            />
            <span>
              <Emphasized text={b} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function LayerPage() {
  const { layer } = useParams<{ layer: string }>()
  const detail = layer && layer in LAYER_DETAILS ? LAYER_DETAILS[layer as LayerSlug] : undefined
  if (!detail) return <Navigate to="/how-it-works" replace />

  const dotClass = LAYERS.find((l) => l.slug === detail.slug)!.dotClass

  return (
    <div className="mx-auto max-w-[860px] space-y-12 pt-6 pb-28">
      <Link
        to="/how-it-works"
        className="text-secondary-foreground hover:text-primary inline-flex items-center gap-1.5 text-[12.5px] font-semibold transition-colors duration-150"
      >
        <ArrowLeft className="size-3.5" strokeWidth={1.75} />
        {BACK_TO_OVERVIEW}
      </Link>

      {/* 页头:识别色 + 标题 + 主角句 + 示例 chips */}
      <Screen className="space-y-5">
        <div className="flex items-center gap-3">
          <span aria-hidden className={`size-2.5 rounded-full ${dotClass}`} />
          <ScreenTitle>{detail.title}</ScreenTitle>
        </div>
        <Lede text={detail.leadLine} />
        <div className="flex flex-wrap gap-2">
          {detail.examples.map((ex) => (
            <span
              key={ex}
              className="text-secondary-foreground rounded-[var(--radius-pill)] border border-[var(--border-strong)] px-3.5 py-1.5 text-[12.5px] font-medium"
            >
              {ex}
            </span>
          ))}
        </div>
      </Screen>

      {/* 四张关键词卡(业务介入高亮) */}
      <Screen>
        <div className="grid gap-4 md:grid-cols-2">
          {detail.cards.map((card) => (
            <KeywordCard key={card.heading} {...card} />
          ))}
        </div>
      </Screen>

      {/* 回答时:may / may not */}
      <Screen className="space-y-5">
        <SectionHeading>At answer time, the model…</SectionHeading>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="bg-success-soft rounded-[16px] px-5 py-5">
            <p className="text-success text-[13px] font-semibold tracking-[0.06em] uppercase">
              May
            </p>
            <ul className="mt-3 space-y-2">
              {detail.answerTime.may.map((item) => (
                <li key={item} className="text-foreground flex gap-2.5 text-[14px] leading-[1.55]">
                  <Check className="text-success-dot mt-[3px] size-3.5 shrink-0" strokeWidth={2} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-destructive-soft rounded-[16px] px-5 py-5">
            <p className="text-destructive text-[13px] font-semibold tracking-[0.06em] uppercase">
              May not
            </p>
            <ul className="mt-3 space-y-2">
              {detail.answerTime.mayNot.map((item) => (
                <li key={item} className="text-foreground flex gap-2.5 text-[14px] leading-[1.55]">
                  <X className="text-destructive mt-[3px] size-3.5 shrink-0" strokeWidth={2} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Screen>

      {/* 刻意不做 */}
      <Screen className="space-y-5">
        <SectionHeading>Deliberately doesn’t</SectionHeading>
        <ul className="space-y-2.5">
          {detail.doesNot.map((item) => (
            <li
              key={item}
              className="text-secondary-foreground flex gap-3 text-[15px] leading-[1.55]"
            >
              <span
                aria-hidden
                className="bg-border-strong mt-[9px] size-[5px] shrink-0 rounded-full"
              />
              <span>
                <Emphasized text={item} />
              </span>
            </li>
          ))}
        </ul>
      </Screen>

      <Link
        to="/how-it-works"
        className="text-secondary-foreground hover:text-primary inline-flex items-center gap-1.5 text-[12.5px] font-semibold transition-colors duration-150"
      >
        <ArrowLeft className="size-3.5" strokeWidth={1.75} />
        {BACK_TO_OVERVIEW}
      </Link>
    </div>
  )
}
