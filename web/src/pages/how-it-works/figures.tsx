/**
 * 说明页的图。
 *
 * 全部用既有 token 的填充块 + flex 画,**不引任何图表库**;文字只放关键词。
 * 不用内联 SVG:图里的说明句较长,SVG <text> 不换行、窄屏必溢出;填充块天然自适应。
 *
 * 总页:FunnelFigure(倒漏斗,块宽递增 = 模型自由度递增)、GateFigure(治理骨架四步)
 * 架构页:StackFigure(六层技术架构)、ShellCoreFigure(外壳/内核)、
 *         RequestPathFigure(一次请求)、JourneyFigure(两个角色的闭环)、
 *         EvaluationFigure(四层评估)、AutonomyFigure(自主性边界)
 * 子页:  FlowFigure(治理期 / 回答期两条流程,通用)
 */
import { ArrowUp, CornerDownLeft } from 'lucide-react'

import {
  AUTONOMY,
  EVALUATION,
  FUNNEL,
  GATE,
  JOURNEY,
  REQUEST_PATH,
  SHELL_CORE,
  STACK,
  type FlowStep,
} from './content'
import { Emphasized, Meta } from './Section'

/** 总页:倒漏斗 —— 自上而下四层,块宽递增 */
export function FunnelFigure() {
  const widths = ['58%', '72%', '86%', '100%']
  return (
    <figure className="space-y-3">
      <div className="space-y-2">
        {FUNNEL.layers.map((layer, i) => (
          <div
            key={layer.label}
            className="bg-subtle flex min-w-[260px] items-center gap-2.5 rounded-[13px] px-4 py-3"
            style={{ width: widths[i] }}
          >
            <span aria-hidden className={`size-2 shrink-0 rounded-full ${layer.dotClass}`} />
            <span className="text-foreground text-[15px] font-semibold whitespace-nowrap">
              {layer.label}
            </span>
            <span className="text-faint text-[13px]">{layer.note}</span>
          </div>
        ))}
      </div>
      <Meta className="flex flex-wrap gap-x-6 gap-y-1">
        {FUNNEL.axes.map((axis) => (
          <span key={axis}>{axis}</span>
        ))}
      </Meta>
    </figure>
  )
}

/** 总页:治理骨架四步(第 3 步是闸门,黄色识别条) */
export function GateFigure() {
  return (
    <figure className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {GATE.steps.map((step, i) => (
        <div
          key={step.name}
          className={
            i === 2
              ? 'border-accent bg-subtle rounded-[16px] border-l-[3px] px-4 py-4'
              : 'bg-subtle rounded-[16px] px-4 py-4'
          }
        >
          <span className="text-fainter font-mono text-[11px]">{`0${i + 1}`}</span>
          <p className="text-foreground mt-1 text-[15px] font-semibold">{step.name}</p>
          <p className="text-faint mt-2 text-[13px] leading-[1.6]">{step.keywords}</p>
        </div>
      ))}
    </figure>
  )
}

/* ═════════════════════════ 架构页 ═════════════════════════ */

/** 架构页:六层技术架构。自上而下 = 面向用户 → 面向供应商,箭头向上 = 谁支撑谁 */
export function StackFigure() {
  return (
    <figure>
      {STACK.tiers.map((tier, i) => (
        <div key={tier.name}>
          <div className="bg-subtle grid gap-3 rounded-[16px] px-5 py-4 md:grid-cols-[190px_1fr] md:items-center">
            <div>
              <p className="font-display text-foreground text-[15px] font-semibold">{tier.name}</p>
              <p className="text-fainter mt-0.5 text-[12px] leading-[1.45]">{tier.owner}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {tier.blocks.map((block) => (
                <span
                  key={block}
                  className="bg-card text-secondary-foreground rounded-[10px] border border-[var(--border-strong)] px-3 py-2 text-[13px] leading-[1.3]"
                >
                  {block}
                </span>
              ))}
            </div>
          </div>
          {i < STACK.tiers.length - 1 && (
            <div className="flex justify-center py-1.5">
              <ArrowUp aria-hidden className="text-fainter size-4" strokeWidth={1.75} />
            </div>
          )}
        </div>
      ))}
    </figure>
  )
}

/** 架构页:确定性外壳包住有限自主的内核 */
export function ShellCoreFigure() {
  return (
    <figure className="rounded-[18px] border border-[var(--border-strong)] p-5">
      <p className="text-muted-foreground text-[11px] font-semibold tracking-[0.06em] uppercase">
        {SHELL_CORE.shellLabel}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {SHELL_CORE.shell.map((item) => (
          <span
            key={item}
            className="bg-muted text-secondary-foreground rounded-[var(--radius-pill)] px-3 py-1.5 text-[12.5px]"
          >
            {item}
          </span>
        ))}
      </div>
      <div className="bg-primary-soft mt-4 rounded-[16px] px-5 py-5">
        <p className="text-primary text-[11px] font-semibold tracking-[0.06em] uppercase">
          {SHELL_CORE.coreLabel}
        </p>
        <ul className="mt-3 space-y-2">
          {SHELL_CORE.core.map((item) => (
            <li key={item} className="text-foreground flex gap-2.5 text-[14px] leading-[1.55]">
              <span aria-hidden className="bg-primary mt-[8px] size-[4px] shrink-0 rounded-full" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  )
}

const TONE_DOT: Record<string, string> = {
  neutral: 'bg-border-strong',
  exact: 'bg-kb-exact-qa',
  text2sql: 'bg-kb-text2sql',
  document: 'bg-kb-document',
  none: 'bg-fainter',
}

/** 架构页:一次请求的全链路(命中 / 未命中 两个出口写在每一步上) */
export function RequestPathFigure() {
  return (
    <figure>
      {REQUEST_PATH.steps.map((step, i) => {
        const isLast = i === REQUEST_PATH.steps.length - 1
        return (
          <div key={step.name} className="flex gap-4">
            <div className="flex flex-col items-center pt-[7px]">
              <span
                aria-hidden
                className={`size-[9px] shrink-0 rounded-full ${TONE_DOT[step.tone]}`}
              />
              {!isLast && <span aria-hidden className="bg-border w-px flex-1" />}
            </div>
            <div className={isLast ? 'min-w-0 pb-0' : 'min-w-0 pb-6'}>
              <p className="text-foreground text-[16px] font-semibold">{step.name}</p>
              <p className="text-fainter mt-0.5 font-mono text-[11px]">{step.who}</p>
              <p className="text-secondary-foreground mt-1.5 text-[14px] leading-[1.6]">
                {step.detail}
              </p>
              {(step.hit || step.miss) && (
                <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
                  {step.hit && (
                    <p className="bg-success-soft text-foreground rounded-[12px] px-3.5 py-2.5 text-[13px] leading-[1.5]">
                      <Emphasized text={step.hit} />
                    </p>
                  )}
                  {step.miss && (
                    <p className="bg-muted text-secondary-foreground rounded-[12px] px-3.5 py-2.5 text-[13px] leading-[1.5]">
                      <Emphasized text={step.miss} />
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )
      })}
      <div className="border-border-soft mt-7 border-t pt-4">
        <p className="text-muted-foreground text-[11px] font-semibold tracking-[0.06em] uppercase">
          {REQUEST_PATH.tracedLabel}
        </p>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {REQUEST_PATH.traced.map((item) => (
            <span
              key={item}
              className="bg-subtle text-secondary-foreground rounded-[var(--radius-pill)] px-3 py-1.5 text-[12.5px]"
            >
              {item}
            </span>
          ))}
        </div>
      </div>
    </figure>
  )
}

const WHO_DOT: Record<string, string> = {
  ops: 'bg-accent',
  user: 'bg-primary',
  system: 'bg-border-strong',
}

/** 架构页:两个角色的闭环(末尾回到 01) */
export function JourneyFigure() {
  return (
    <figure className="space-y-4">
      <div className="flex flex-wrap gap-x-6 gap-y-1.5">
        {JOURNEY.legend.map((l) => (
          <span key={l.key} className="text-faint flex items-center gap-2 text-[12.5px]">
            <span aria-hidden className={`size-2 rounded-full ${WHO_DOT[l.key]}`} />
            {l.label}
          </span>
        ))}
      </div>
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
        {JOURNEY.stages.map((stage, i) => (
          <div key={stage.name} className="bg-subtle rounded-[14px] px-4 py-3.5">
            <span className="flex items-center gap-2">
              <span aria-hidden className={`size-2 shrink-0 rounded-full ${WHO_DOT[stage.who]}`} />
              <span className="text-fainter font-mono text-[11px]">{`0${i + 1}`}</span>
            </span>
            <p className="text-foreground mt-1.5 text-[14px] leading-[1.35] font-semibold">
              {stage.name}
            </p>
            <p className="text-faint mt-1 text-[12.5px] leading-[1.5]">{stage.note}</p>
          </div>
        ))}
        <div className="border-border-strong flex items-center gap-2.5 rounded-[14px] border border-dashed px-4 py-3.5">
          <CornerDownLeft aria-hidden className="text-fainter size-4 shrink-0" strokeWidth={1.75} />
          <p className="text-faint text-[12.5px] leading-[1.5]">{JOURNEY.returnNote}</p>
        </div>
      </div>
    </figure>
  )
}

/** 架构页:四层评估 */
export function EvaluationFigure() {
  return (
    <figure>
      {EVALUATION.levels.map((lvl, i) => (
        <div
          key={lvl.level}
          className="border-border-soft grid gap-2 border-t py-4 first:border-t-0 first:pt-0 md:grid-cols-[210px_1fr] md:gap-6"
        >
          <div>
            <span className="text-fainter font-mono text-[11px]">{`L${i + 1}`}</span>
            <p className="font-display text-foreground mt-0.5 text-[15px] font-semibold">
              {lvl.level}
            </p>
            <p className="text-faint mt-1 text-[12.5px] leading-[1.5]">{lvl.asks}</p>
          </div>
          <ul className="space-y-1.5">
            {lvl.checks.map((c) => (
              <li
                key={c}
                className="text-secondary-foreground flex gap-2.5 text-[14px] leading-[1.55]"
              >
                <span
                  aria-hidden
                  className="bg-border-strong mt-[8px] size-[4px] shrink-0 rounded-full"
                />
                <span>{c}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </figure>
  )
}

/** 架构页:自主性边界(左宽松 / 右不给) */
export function AutonomyFigure() {
  return (
    <figure className="grid gap-4 md:grid-cols-2">
      <div className="bg-success-soft rounded-[16px] px-5 py-5">
        <p className="text-success text-[11px] font-semibold tracking-[0.06em] uppercase">
          {AUTONOMY.moreLabel}
        </p>
        <ul className="mt-3 space-y-2">
          {AUTONOMY.more.map((item) => (
            <li key={item} className="text-foreground flex gap-2.5 text-[14px] leading-[1.55]">
              <span
                aria-hidden
                className="bg-success-dot mt-[8px] size-[4px] shrink-0 rounded-full"
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="bg-destructive-soft rounded-[16px] px-5 py-5">
        <p className="text-destructive text-[11px] font-semibold tracking-[0.06em] uppercase">
          {AUTONOMY.lessLabel}
        </p>
        <ul className="mt-3 space-y-2">
          {AUTONOMY.less.map((item) => (
            <li key={item} className="text-foreground flex gap-2.5 text-[14px] leading-[1.55]">
              <span
                aria-hidden
                className="bg-destructive mt-[8px] size-[4px] shrink-0 rounded-full"
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  )
}

/* ═════════════════════════ 子页:两条流程 ═════════════════════════ */

/** 子页:一条流程(治理期 / 回答期通用)。
 *  kind:gate = 闸门(黄条),stop = 链路终点(浅底收口),其余是普通步。 */
export function FlowFigure({
  label,
  steps,
  dotClass,
}: {
  label: string
  steps: FlowStep[]
  dotClass: string
}) {
  return (
    <figure className="rounded-[18px] border border-[var(--border-strong)] px-5 py-5">
      <p className="flex items-center gap-2.5">
        <span aria-hidden className={`size-2 shrink-0 rounded-full ${dotClass}`} />
        <span className="text-muted-foreground text-[11px] font-semibold tracking-[0.06em] uppercase">
          {label}
        </span>
      </p>
      <div className="mt-4">
        {steps.map((step, i) => {
          const isLast = i === steps.length - 1
          return (
            <div key={step.name} className="flex gap-3.5">
              <div className="flex flex-col items-center pt-[6px]">
                <span
                  aria-hidden
                  className={
                    step.kind === 'gate'
                      ? 'bg-accent size-[9px] shrink-0 rounded-full'
                      : step.kind === 'stop'
                        ? 'bg-fainter size-[9px] shrink-0 rounded-full'
                        : 'bg-border-strong size-[9px] shrink-0 rounded-full'
                  }
                />
                {!isLast && <span aria-hidden className="bg-border w-px flex-1" />}
              </div>
              <div className={isLast ? 'min-w-0 pb-0' : 'min-w-0 pb-4'}>
                <p className="text-foreground text-[15px] leading-[1.35] font-semibold">
                  {step.name}
                  {step.kind === 'gate' && (
                    <span className="bg-accent-soft text-accent-ink ml-2 rounded-[var(--radius-pill)] px-2 py-0.5 align-middle text-[10.5px] font-semibold tracking-[0.04em] uppercase">
                      gate
                    </span>
                  )}
                  {step.kind === 'stop' && (
                    <span className="bg-muted text-muted-foreground ml-2 rounded-[var(--radius-pill)] px-2 py-0.5 align-middle text-[10.5px] font-semibold tracking-[0.04em] uppercase">
                      end
                    </span>
                  )}
                </p>
                <p className="text-faint mt-0.5 text-[13px] leading-[1.55]">{step.note}</p>
              </div>
            </div>
          )
        })}
      </div>
    </figure>
  )
}
