/**
 * `/how-it-works` 总页。结构(2026-08-27 v4,图先于字):
 *
 *   主张句 + **全局图**(SystemMapFigure) → **两级路由图**(RoutingFigure)+ R1–R3 →
 *   四种知识的卡片(例子 chips + 自由度计量条) → 一次请求(判定流程图) →
 *   架构段(标题 + 四条立场常驻,其余五小节折叠) → 九个折叠区 →
 *   **收尾:第四种知识 · 编排**(#workflows) → 署名
 *
 * v4 要点:常驻区四块**每块都由一张图领队**,文字退成图注 ——
 * 第 1 块一张全局图先把「谁决定什么」讲完(两个时钟 + 知识中枢 + 回边 + 留痕),
 * 后三块依次放大:路由顺序 → 三层是什么 → 一次请求逐步判定。
 * v5(同日,需求方纠正):**层级关系** —— 精准问答 / 智能问数 / 编排三者同级(都注册意图),
 * 文档 RAG 是兜底,由 `RoutingFigure` 画;卡片区因此变四张(第四张链到收尾那一节,
 * 它没有子页)。收尾一节把编排讲完:概念图 + 四条纪律 + 那条客服邮件逐节点的例子。
 * 下面 9 个折叠区(架构五小节 + 原四区)默认收起,折叠态标题 + 结论句摘要就是目录;
 * 投屏讲解场景用折叠组顶部的 Expand all 一键还原全展开。
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
  FREEDOM_LABEL,
  GATE,
  JOURNEY,
  KIND_CARD_ORDER,
  LAYER_CARDS_TITLE,
  LAYER_DETAILS,
  LAYERS,
  PAIN_POINTS,
  PRINCIPLES,
  REQUEST_PATH,
  ROUTING,
  SHELL_CORE,
  STACK,
  SYSTEM_MAP,
  TRADEOFFS,
  WORKFLOW,
  WORKFLOW_CARD,
  WORKFLOW_EXAMPLE,
} from './content'
import {
  AutonomyFigure,
  EvaluationFigure,
  FreedomMeter,
  GateFigure,
  JourneyFigure,
  RequestPathFigure,
  RoutingFigure,
  ShellCoreFigure,
  StackFigure,
  SystemMapFigure,
  WorkflowConceptFigure,
  WorkflowExampleFigure,
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

/** 四张卡片共用的外框(三层是 <Link> 进子页,编排是 <a> 滚到收尾那一节) */
const KIND_CARD_CLASS =
  'group flex flex-col rounded-[var(--radius-card)] border border-[var(--border)] p-6 shadow-[var(--shadow-card)] transition-all duration-150 hover:border-[var(--border-strong)]'

function KindCardBody({
  name,
  dotClass,
  leadLine,
  examples,
  freedom,
  linkLabel,
  badge,
}: {
  name: string
  dotClass: string
  leadLine: string
  examples: string[]
  freedom: number
  linkLabel: string
  badge?: string
}) {
  return (
    <>
      <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span aria-hidden className={`size-2 rounded-full ${dotClass}`} />
        <span className="font-display text-foreground text-[17px] font-semibold">{name}</span>
        {badge && (
          <span className="bg-muted text-muted-foreground rounded-[var(--radius-pill)] px-2 py-0.5 text-[10.5px] font-semibold tracking-[0.04em] uppercase">
            {badge}
          </span>
        )}
      </span>
      <span className="text-secondary-foreground mt-3 flex-1 text-[14px] leading-[1.6]">
        <Emphasized text={leadLine} />
      </span>
      <span className="mt-3 flex flex-wrap gap-1.5">
        {examples.map((example) => (
          <span
            key={example}
            className="bg-muted text-secondary-foreground rounded-[var(--radius-pill)] px-2.5 py-1 text-[11.5px]"
          >
            {example}
          </span>
        ))}
      </span>
      <span className="border-border-soft mt-4 flex items-center gap-2.5 border-t pt-3.5">
        <FreedomMeter level={freedom} dotClass={dotClass} />
        <span className="text-faint text-[11.5px]">{FREEDOM_LABEL}</span>
      </span>
      <span className="text-primary mt-4 flex items-center gap-1.5 text-[12.5px] font-semibold">
        {linkLabel}
        <ArrowRight
          className="size-3.5 transition-transform duration-150 group-hover:translate-x-0.5"
          strokeWidth={1.75}
        />
      </span>
    </>
  )
}

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
      {/* 常驻块 1:主张句 + 全局图 —— 冷读者的第一眼,整页唯一的「一图看懂」 */}
      <div className="space-y-7">
        <div className="space-y-4">
          <ClaimHeadline>{CLAIM.headline}</ClaimHeadline>
          <Lede text={CLAIM.lede} />
        </div>
        <div className="space-y-3">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <SectionHeading>{SYSTEM_MAP.title}</SectionHeading>
            <Meta>{SYSTEM_MAP.summary}</Meta>
          </div>
          <SystemMapFigure />
        </div>
      </div>

      {/* 常驻块 2:两级路由(三家同级 + 兜底)+ 三条推论 */}
      <div className="border-border-soft mt-16 border-t pt-10">
        <div className="space-y-7">
          <div className="space-y-2">
            <ScreenTitle>{ROUTING.title}</ScreenTitle>
            <Meta>{ROUTING.summary}</Meta>
          </div>
          <RoutingFigure />
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
      </div>

      {/* 常驻块 3:四种知识的卡片(前三张进子页,第四张滚到收尾那一节) */}
      <div className="border-border-soft mt-16 border-t pt-10">
        <div className="space-y-6">
          <ScreenTitle>{LAYER_CARDS_TITLE}</ScreenTitle>
          {/* 顺序出自 content 的 KIND_CARD_ORDER:两家意图层 → 编排 → 文档兜底 */}
          <div className="grid gap-4 md:grid-cols-2">
            {KIND_CARD_ORDER.map((key) => {
              if (key === 'workflow') {
                return (
                  <a key={key} href={WORKFLOW_CARD.href} className={KIND_CARD_CLASS}>
                    <KindCardBody
                      name={WORKFLOW_CARD.name}
                      dotClass={WORKFLOW_CARD.dotClass}
                      leadLine={WORKFLOW_CARD.leadLine}
                      examples={WORKFLOW_CARD.examples}
                      freedom={WORKFLOW_CARD.freedom}
                      linkLabel={WORKFLOW_CARD.linkLabel}
                      badge={WORKFLOW_CARD.badge}
                    />
                  </a>
                )
              }
              const layer = LAYERS.find((l) => l.slug === key)!
              return (
                <Link key={key} to={`/how-it-works/${key}`} className={KIND_CARD_CLASS}>
                  <KindCardBody
                    name={layer.name}
                    dotClass={layer.dotClass}
                    leadLine={layer.leadLine}
                    examples={LAYER_DETAILS[key].examples}
                    freedom={layer.freedom}
                    linkLabel="Read on"
                  />
                </Link>
              )
            })}
          </div>
        </div>
      </div>

      {/* 常驻块 4:一次请求的判定流程图(命中往右出 / 未命中往下走) */}
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

      {/* 常驻块 5:架构段开场 —— 标题 + lede + 四条立场;其余五小节在下面的折叠组 */}
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
            {[...LAYERS, WORKFLOW_CARD].map((kind) => (
              <p key={kind.name} className="flex items-center gap-2.5 text-[14px]">
                <span aria-hidden className={`size-2 shrink-0 rounded-full ${kind.dotClass}`} />
                <span className="text-foreground font-semibold">{kind.name}</span>
                <span className="text-faint">{kind.positioning}</span>
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
            <table className="w-full min-w-[780px] border-collapse text-left">
              <thead>
                <tr>
                  <th className="w-[140px] pb-3" />
                  {COMPARISON.columns.map((col, i) => (
                    <th
                      key={col}
                      className="text-muted-foreground pb-3 pl-5 text-[11px] font-semibold tracking-[0.06em] uppercase"
                    >
                      <span className="flex items-center gap-2">
                        <span aria-hidden className={`size-2 rounded-full ${COMPARISON.dots[i]}`} />
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

      {/* 收尾常驻块:第四种知识 —— 编排(卡片区第四张卡链到这里)。
          纪律:它必须自己说清「已设计、未落地」,动作节点仍守 AUTONOMY 那条线 */}
      <section id="workflows" className="border-border-soft mt-16 scroll-mt-20 border-t pt-10">
        <div className="space-y-7">
          <div className="space-y-4">
            <ScreenTitle>{WORKFLOW.title}</ScreenTitle>
            <Lede text={WORKFLOW.lede} />
          </div>

          <div className="space-y-3">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <SectionHeading>{WORKFLOW.builtFromLabel}</SectionHeading>
              <Meta>{WORKFLOW.summary}</Meta>
            </div>
            <p className="text-secondary-foreground text-[15px] leading-[1.6]">
              {WORKFLOW.builtFromNote}
            </p>
            <WorkflowConceptFigure />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {WORKFLOW.rules.map((rule, i) => (
              <div key={rule.head} className="bg-subtle rounded-[16px] px-5 py-5">
                <span className="text-fainter font-mono text-[11px]">{`W${i + 1}`}</span>
                <p className="text-foreground mt-1.5 text-[16px] leading-[1.4] font-semibold">
                  {rule.head}
                </p>
                <p className="border-border-soft text-faint mt-3 border-t pt-3 text-[13.5px] leading-[1.55]">
                  {rule.body}
                </p>
              </div>
            ))}
          </div>

          <p className="border-border-strong flex flex-wrap items-baseline gap-x-2.5 rounded-[14px] border border-dashed px-4 py-3">
            <span className="text-muted-foreground font-mono text-[10.5px] tracking-[0.06em] uppercase">
              {WORKFLOW.statusLabel}
            </span>
            <span className="text-faint text-[13px] leading-[1.55]">{WORKFLOW.status}</span>
          </p>

          <div className="space-y-3 pt-2">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <SectionHeading>{WORKFLOW_EXAMPLE.title}</SectionHeading>
              <Meta>{WORKFLOW_EXAMPLE.summary}</Meta>
            </div>
            <Meta>{WORKFLOW_EXAMPLE.scenario}</Meta>
            <WorkflowExampleFigure />
          </div>

          <Emphasis text={WORKFLOW_EXAMPLE.emphasis} />
        </div>
      </section>

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
