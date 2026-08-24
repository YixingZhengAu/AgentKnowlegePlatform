/**
 * `/how-it-works` 总页。结构(2026-08-24 需求方定,替代原先从上滚到底的八屏):
 *
 *   主张块(常驻) → 三层卡片(常驻,提前) → 六个折叠区(默认收起 = 目录)
 *
 * 讲解时点哪讲哪,不逼观众翻长页。只渲染 content.ts 的数据;字阶走 Section.tsx。
 */
import { ArrowRight, MoveRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import {
  ANSWER_FLOW,
  CLAIM,
  COMPARISON,
  GATE,
  LAYER_CARDS_TITLE,
  LAYERS,
  PAIN_POINTS,
  ROLES,
  TRADEOFFS,
} from './content'
import { AnswerFlowFigure, FunnelFigure, GateFigure, RolesFigure } from './figures'
import {
  ClaimHeadline,
  CollapsibleScreen,
  Emphasis,
  Emphasized,
  Lede,
  ScreenTitle,
} from './Section'

export function OverviewPage() {
  return (
    <div className="mx-auto max-w-[860px] pt-6 pb-28">
      {/* 常驻块 1:主张 + 倒漏斗 + 三条推论 */}
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

      {/* 常驻块 2:三层卡片(进子页) */}
      <div className="mt-16 space-y-6">
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

      {/* 六个折叠区:默认收起,折叠态就是目录 */}
      <div className="mt-16">
        <CollapsibleScreen id="pain-points" title={PAIN_POINTS.title} summary={PAIN_POINTS.summary}>
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

        <CollapsibleScreen id="one-gate" title={GATE.title} summary={GATE.summary}>
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

        <CollapsibleScreen id="answer-flow" title={ANSWER_FLOW.title} summary={ANSWER_FLOW.summary}>
          <AnswerFlowFigure />
          <Emphasis text={ANSWER_FLOW.emphasis} />
        </CollapsibleScreen>

        <CollapsibleScreen id="roles" title={ROLES.title} summary={ROLES.summary}>
          <RolesFigure />
          <Emphasis text={ROLES.emphasis} />
        </CollapsibleScreen>

        <CollapsibleScreen id="comparison" title={COMPARISON.title} summary={COMPARISON.summary}>
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

        <CollapsibleScreen id="tradeoffs" title={TRADEOFFS.title} summary={TRADEOFFS.summary}>
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
    </div>
  )
}
