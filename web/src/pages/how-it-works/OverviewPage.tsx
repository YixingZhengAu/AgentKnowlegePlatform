/**
 * `/how-it-works` 总页。结构(2026-08-26 v2.1):
 *
 *   主张块 → 四条立场 → 架构段(六小节 + 锚点条) → 三层卡片 →
 *   四个折叠区(默认收起 = 目录) → 署名
 *
 * 架构段一度是独立子页 `/how-it-works/architecture`,已并回本页:
 * 「为什么这么设计 → 结构长什么样」本来就是一条论证,拆两页反而要来回跳;
 * 「一层怎么做」仍在三个层子页。长度靠锚点条与折叠区控制。
 * 只渲染 content.ts 的数据;字阶走 Section.tsx。
 */
import { ArrowRight, MoveRight } from 'lucide-react'
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
  Screen,
  ScreenTitle,
  SectionHeading,
} from './Section'

/** 架构段的锚点条(顺序 = 下面 <Screen> 的顺序) */
const ANCHORS = [
  { id: 'stack', label: STACK.title },
  { id: 'shell-core', label: SHELL_CORE.title },
  { id: 'request-path', label: REQUEST_PATH.title },
  { id: 'journey', label: JOURNEY.title },
  { id: 'evaluation', label: EVALUATION.title },
  { id: 'autonomy', label: AUTONOMY.title },
]

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

      {/* 常驻块 2:四条立场(整套架构的论证起点) */}
      <div className="mt-16 space-y-6">
        <ScreenTitle>{PRINCIPLES.title}</ScreenTitle>
        <div className="grid gap-4 md:grid-cols-2">
          {PRINCIPLES.items.map((item, i) => (
            <div key={item.line} className="bg-subtle flex flex-col rounded-[16px] px-5 py-5">
              <span className="text-fainter font-mono text-[11px]">{`P${i + 1}`}</span>
              <p className="text-foreground mt-1.5 text-[16px] leading-[1.4] font-semibold">
                {item.line}
              </p>
              <p className="border-border-soft text-faint mt-auto border-t pt-3 text-[13.5px] leading-[1.55]">
                {item.here}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* 常驻块 3:架构段 —— 六小节,顶部锚点条 */}
      <div className="border-border-soft mt-16 border-t pt-10">
        <div className="space-y-4">
          <ScreenTitle>{ARCHITECTURE.title}</ScreenTitle>
          <Lede text={ARCHITECTURE.lede} />
          <nav className="flex flex-wrap gap-2 pt-1">
            {ANCHORS.map((a) => (
              <a
                key={a.id}
                href={`#${a.id}`}
                className="text-secondary-foreground hover:text-primary rounded-[var(--radius-pill)] border border-[var(--border-strong)] px-3.5 py-1.5 text-[12.5px] font-medium transition-colors duration-150"
              >
                {a.label}
              </a>
            ))}
          </nav>
        </div>

        <div className="mt-12 space-y-16">
          {/* 1. 六层技术架构 */}
          <Screen id="stack">
            <div className="space-y-2">
              <SectionHeading>{STACK.title}</SectionHeading>
              <Meta>{STACK.summary}</Meta>
            </div>
            <StackFigure />
            <div className="space-y-2">
              {STACK.notes.map((n) => (
                <p key={n} className="text-secondary-foreground text-[15px] leading-[1.6]">
                  {n}
                </p>
              ))}
            </div>
            <Emphasis text={STACK.emphasis} />
          </Screen>

          {/* 2. 确定性外壳 + 有限自主内核 */}
          <Screen id="shell-core">
            <div className="space-y-2">
              <SectionHeading>{SHELL_CORE.title}</SectionHeading>
              <Meta>{SHELL_CORE.summary}</Meta>
            </div>
            <ShellCoreFigure />
            <Emphasis text={SHELL_CORE.emphasis} />
          </Screen>

          {/* 3. 一次请求 */}
          <Screen id="request-path">
            <div className="space-y-2">
              <SectionHeading>{REQUEST_PATH.title}</SectionHeading>
              <Meta>{REQUEST_PATH.summary}</Meta>
            </div>
            <RequestPathFigure />
            <Emphasis text={REQUEST_PATH.emphasis} />
          </Screen>

          {/* 4. 两个角色的闭环 */}
          <Screen id="journey">
            <div className="space-y-2">
              <SectionHeading>{JOURNEY.title}</SectionHeading>
              <Meta>{JOURNEY.summary}</Meta>
            </div>
            <JourneyFigure />
            <Emphasis text={JOURNEY.emphasis} />
          </Screen>

          {/* 5. 四层评估 */}
          <Screen id="evaluation">
            <div className="space-y-2">
              <SectionHeading>{EVALUATION.title}</SectionHeading>
              <Meta>{EVALUATION.summary}</Meta>
            </div>
            <EvaluationFigure />
            <Emphasis text={EVALUATION.emphasis} />
          </Screen>

          {/* 6. 自主性边界 */}
          <Screen id="autonomy">
            <div className="space-y-2">
              <SectionHeading>{AUTONOMY.title}</SectionHeading>
              <Meta>{AUTONOMY.summary}</Meta>
            </div>
            <AutonomyFigure />
            <Emphasis text={AUTONOMY.emphasis} />
          </Screen>
        </div>
      </div>

      {/* 常驻块 4:三层卡片(进子页) */}
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

      {/* 四个折叠区:默认收起,折叠态就是目录 */}
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
