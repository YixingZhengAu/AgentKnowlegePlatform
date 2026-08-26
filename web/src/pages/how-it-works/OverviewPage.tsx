/**
 * `/how-it-works` 总页。结构(2026-08-26 v3,自读优先):
 *
 *   主张块(漏斗带例句) → 三层卡片(带例子 chips) → 一次请求(常驻) →
 *   架构段(标题 + 四条立场常驻,其余五小节折叠) →
 *   四个折叠区 → 署名
 *
 * v3 要点:前三屏 = 冷读者自读就能拿走的完整故事;下面 9 个折叠区
 * (架构五小节 + 原四区)默认收起,折叠态标题 + 结论句摘要就是目录;
 * 投屏讲解场景用折叠组顶部的 Expand all 一键还原全展开(v2.1 形态)。
 * 锚点条已删(折叠列表取代其目录功能)。
 * 只渲染 content.ts 的数据;字阶走 Section.tsx。
 */
import { ArrowRight, MoveRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import {
  ARCHITECTURE,
  AUTHORS,
  AUTONOMY,
  CLAIM,
  COMPARISON,
  EVALUATION,
  GATE,
  JOURNEY,
  LAYER_CARDS_TITLE,
  LAYER_DETAILS,
  LAYERS,
  PAIN_POINTS,
  PRINCIPLES,
  REQUEST_PATH,
  SHELL_CORE,
  STACK,
  TRADEOFFS,
} from './content'
import {
  AutonomyFigure,
  EvaluationFigure,
  FunnelFigure,
  GateFigure,
  JourneyFigure,
  RequestPathFigure,
  ShellCoreFigure,
  StackFigure,
} from './figures'
import {
  ClaimHeadline,
  CollapsibleScreen,
  Emphasis,
  Emphasized,
  Lede,
  Meta,
  ScreenTitle,
  SectionHeading,
} from './Section'

/** 全部折叠区的 id(顺序 = 页面顺序),Expand all / Collapse all 以它为准 */
const COLLAPSIBLE_IDS = [
  'stack',
  'shell-core',
  'journey',
  'evaluation',
  'autonomy',
  'pain-points',
  'one-gate',
  'comparison',
  'tradeoffs',
]

export function OverviewPage() {
  const [openIds, setOpenIds] = useState<ReadonlySet<string>>(new Set())
  const allOpen = openIds.size === COLLAPSIBLE_IDS.length
  const toggleOne = (id: string) =>
    setOpenIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const toggleAll = () => setOpenIds(allOpen ? new Set() : new Set(COLLAPSIBLE_IDS))
  const collapsibleProps = (id: string) => ({
    id,
    open: openIds.has(id),
    onToggle: () => toggleOne(id),
  })

  return (
    <div className="mx-auto max-w-[860px] pt-6 pb-28">
      {/* 常驻块 1:主张 + 倒漏斗(带例句) + 三条推论 */}
      <div className="space-y-8">
        <div className="space-y-4">
          <ClaimHeadline>{CLAIM.headline}</ClaimHeadline>
          <Lede text={CLAIM.lede} />
        </div>
        <FunnelFigure />
        <div className="grid gap-4 md:grid-cols-3">
          {CLAIM.corollaries.map((c, i) => (
            <div key={c.title} className="bg-subtle rounded-[16px] px-5 py-5">
              <span className="text-fainter font-mono text-[11px]">{`R${i + 1}`}</span>
              <p className="font-display text-foreground mt-1 text-[17px] leading-[1.3] font-semibold">
                {c.title}
              </p>
              <ul className="mt-3 space-y-1.5">
                {c.points.map((point) => (
                  <li
                    key={point}
                    className="text-secondary-foreground text-[13.5px] leading-[1.55]"
                  >
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <Emphasis text={CLAIM.emphasis} />
      </div>

      {/* 常驻块 2:三层卡片(带例子 chips,进子页)。冷读者先知道"三层是什么" */}
      <div className="border-border-soft mt-16 border-t pt-10">
        <div className="space-y-6">
          <ScreenTitle>{LAYER_CARDS_TITLE}</ScreenTitle>
          <div className="grid gap-4 lg:grid-cols-3">
            {LAYERS.map((layer) => (
              <Link
                key={layer.slug}
                to={`/how-it-works/${layer.slug}`}
                className="group flex flex-col rounded-[var(--radius-card)] border border-[var(--border)] p-6 shadow-[var(--shadow-card)] transition-all duration-150 hover:border-[var(--border-strong)]"
              >
                <span className="flex items-center gap-2.5">
                  <span aria-hidden className={`size-2 rounded-full ${layer.dotClass}`} />
                  <span className="font-display text-foreground text-[17px] font-semibold">
                    {layer.name}
                  </span>
                </span>
                <span className="text-secondary-foreground mt-3 flex-1 text-[14px] leading-[1.6]">
                  <Emphasized text={layer.leadLine} />
                </span>
                <span className="mt-3 flex flex-wrap gap-1.5">
                  {LAYER_DETAILS[layer.slug].examples.map((example) => (
                    <span
                      key={example}
                      className="bg-muted text-secondary-foreground rounded-[var(--radius-pill)] px-2.5 py-1 text-[11.5px]"
                    >
                      {example}
                    </span>
                  ))}
                </span>
                <span className="text-primary mt-5 flex items-center gap-1.5 text-[12.5px] font-semibold">
                  Read on
                  <ArrowRight
                    className="size-3.5 transition-transform duration-150 group-hover:translate-x-0.5"
                    strokeWidth={1.75}
                  />
                </span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {/* 常驻块 3:一次请求的全链路(自读者最直觉的入口,从架构段拎出独立成块) */}
      <div className="border-border-soft mt-16 border-t pt-10">
        <div className="space-y-7">
          <div className="space-y-2">
            <ScreenTitle>{REQUEST_PATH.title}</ScreenTitle>
            <Meta>{REQUEST_PATH.summary}</Meta>
          </div>
          <RequestPathFigure />
          <Emphasis text={REQUEST_PATH.emphasis} />
        </div>
      </div>

      {/* 常驻块 4:架构段开场 —— 标题 + lede + 四条立场;其余五小节在下面的折叠组 */}
      <div className="border-border-soft mt-16 border-t pt-10">
        <div className="space-y-6">
          <div className="space-y-4">
            <ScreenTitle>{ARCHITECTURE.title}</ScreenTitle>
            <Lede text={ARCHITECTURE.lede} />
          </div>
          <SectionHeading>{PRINCIPLES.title}</SectionHeading>
          <div className="grid gap-4 md:grid-cols-2">
            {PRINCIPLES.items.map((item, i) => (
              <div key={item.line} className="bg-subtle rounded-[16px] px-5 py-5">
                <span className="text-fainter font-mono text-[11px]">{`P${i + 1}`}</span>
                <p className="text-foreground mt-1.5 text-[16px] leading-[1.4] font-semibold">
                  {item.line}
                </p>
                <p className="border-border-soft text-faint mt-3 border-t pt-3 text-[13.5px] leading-[1.55]">
                  {item.here}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 折叠组:架构五小节 + 原四区,默认全收起 = 目录;Expand all 给投屏讲解用 */}
      <div className="mt-14">
        <div className="flex justify-end pb-2">
          <button
            onClick={toggleAll}
            className="text-faint hover:text-secondary-foreground text-[13px] font-medium transition-colors duration-150"
          >
            {allOpen ? 'Collapse all' : 'Expand all'}
          </button>
        </div>

        <CollapsibleScreen
          {...collapsibleProps('stack')}
          title={STACK.title}
          summary={STACK.summary}
        >
          <StackFigure />
          <div className="space-y-2">
            {STACK.notes.map((n) => (
              <p key={n} className="text-secondary-foreground text-[15px] leading-[1.6]">
                {n}
              </p>
            ))}
          </div>
          <Emphasis text={STACK.emphasis} />
        </CollapsibleScreen>

        <CollapsibleScreen
          {...collapsibleProps('shell-core')}
          title={SHELL_CORE.title}
          summary={SHELL_CORE.summary}
        >
          <ShellCoreFigure />
          <Emphasis text={SHELL_CORE.emphasis} />
        </CollapsibleScreen>

        <CollapsibleScreen
          {...collapsibleProps('journey')}
          title={JOURNEY.title}
          summary={JOURNEY.summary}
        >
          <JourneyFigure />
          <Emphasis text={JOURNEY.emphasis} />
        </CollapsibleScreen>

        <CollapsibleScreen
          {...collapsibleProps('evaluation')}
          title={EVALUATION.title}
          summary={EVALUATION.summary}
        >
          <EvaluationFigure />
          <Emphasis text={EVALUATION.emphasis} />
        </CollapsibleScreen>

        <CollapsibleScreen
          {...collapsibleProps('autonomy')}
          title={AUTONOMY.title}
          summary={AUTONOMY.summary}
        >
          <AutonomyFigure />
          <Emphasis text={AUTONOMY.emphasis} />
        </CollapsibleScreen>

        <CollapsibleScreen
          {...collapsibleProps('pain-points')}
          title={PAIN_POINTS.title}
          summary={PAIN_POINTS.summary}
        >
          {PAIN_POINTS.rows.map((row) => (
            <div
              key={row.symptom}
              className="border-border-soft grid items-baseline gap-1 border-t py-3.5 first:border-t-0 first:pt-0 md:grid-cols-[1fr_auto_1fr] md:gap-5"
            >
              <p className="text-foreground text-[16px] leading-[1.5] font-semibold">
                {row.symptom}
              </p>
              <MoveRight
                aria-hidden
                className="text-fainter hidden size-4 self-center md:block"
                strokeWidth={1.75}
              />
              <p className="text-secondary-foreground text-[15px] leading-[1.5]">{row.answer}</p>
            </div>
          ))}
        </CollapsibleScreen>

        <CollapsibleScreen
          {...collapsibleProps('one-gate')}
          title={GATE.title}
          summary={GATE.summary}
        >
          <div className="flex flex-wrap gap-x-8 gap-y-2">
            {LAYERS.map((layer) => (
              <p key={layer.slug} className="flex items-center gap-2.5 text-[14px]">
                <span aria-hidden className={`size-2 shrink-0 rounded-full ${layer.dotClass}`} />
                <span className="text-foreground font-semibold">{layer.name}</span>
                <span className="text-faint">{layer.positioning}</span>
              </p>
            ))}
          </div>
          <GateFigure />
          <Emphasis text={GATE.emphasis} />
        </CollapsibleScreen>

        <CollapsibleScreen
          {...collapsibleProps('comparison')}
          title={COMPARISON.title}
          summary={COMPARISON.summary}
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] border-collapse text-left">
              <thead>
                <tr>
                  <th className="w-[140px] pb-3" />
                  {COMPARISON.columns.map((col, i) => (
                    <th
                      key={col}
                      className="text-muted-foreground pb-3 pl-5 text-[11px] font-semibold tracking-[0.06em] uppercase"
                    >
                      <span className="flex items-center gap-2">
                        <span aria-hidden className={`size-2 rounded-full ${LAYERS[i].dotClass}`} />
                        {col}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {COMPARISON.rows.map((row) => (
                  <tr key={row.dimension} className="border-border-soft border-t align-top">
                    <td className="text-foreground py-3.5 pr-4 text-[12.5px] font-semibold">
                      {row.dimension}
                    </td>
                    {row.cells.map((cell) => (
                      <td
                        key={cell}
                        className="text-secondary-foreground py-3.5 pl-5 text-[14px] leading-[1.55]"
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleScreen>

        <CollapsibleScreen
          {...collapsibleProps('tradeoffs')}
          title={TRADEOFFS.title}
          summary={TRADEOFFS.summary}
        >
          <div className="grid gap-3 md:grid-cols-2">
            {TRADEOFFS.items.map((item) => (
              <div key={item.what} className="bg-subtle rounded-[16px] px-5 py-4">
                <p className="text-foreground text-[15px] font-semibold">{item.what}</p>
                <p className="text-faint mt-1 text-[13.5px] leading-[1.55]">{item.why}</p>
              </div>
            ))}
          </div>
        </CollapsibleScreen>
      </div>

      {/* 页脚:署名 */}
      <div className="border-border-soft mt-4 border-t pt-8">
        <p className="text-fainter font-mono text-[11px] tracking-[0.06em] uppercase">
          {AUTHORS.label}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-x-6 gap-y-1">
          {AUTHORS.names.map((name) => (
            <p key={name} className="text-foreground text-[15px] font-semibold">
              {name}
            </p>
          ))}
        </div>
        <p className="text-faint mt-2 text-[13.5px] leading-[1.55]">{AUTHORS.note}</p>
      </div>
    </div>
  )
}
