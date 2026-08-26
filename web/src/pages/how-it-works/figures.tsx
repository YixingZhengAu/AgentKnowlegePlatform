/**
 * 说明页的图。
 *
 * 全部用既有 token 的填充块 + lucide 箭头画,**不引任何图表库**;文字只放关键词。
 * 不用内联 SVG:图里的说明句较长,SVG <text> 不换行、窄屏必溢出;填充块天然自适应。
 *
 * 画法纪律(2026-08-27 v4「图先于字」):**每张图都得看得见方向** ——
 * 步骤之间一律有箭头(`FlowArrow`),分岔一律左右分开(命中往右出、未命中往下走),
 * 闭环一律有回边(虚线 + `CornerDownLeft`)。黄色只有一个含义:人审闸门。
 *
 * 总页常驻:SystemMapFigure(全局图:两个时钟 + 知识中枢 + 回边 + 留痕)、
 *           RoutingFigure(**两级路由**:三家意图并排同级 → 兜底 → 无依据;
 *             2026-08-27 取代旧的四级倒漏斗 FunnelFigure —— 那张图把同级画成了台阶)、
 *           RequestPathFigure(判定流程图:意图那一步**一步三出口**,未命中沿主干往下)、
 *           WorkflowConceptFigure / WorkflowExampleFigure(收尾那一节:第四种知识)
 * 总页折叠:StackFigure(六层 + 供应商接缝)、ShellCoreFigure(外壳/内核)、
 *           JourneyFigure(两段闭环 + 回边)、EvaluationFigure(四级评估链)、
 *           AutonomyFigure(左右分界 + 中间那道线)、GateFigure(治理骨架四步)
 * 子页:    FlowFigure(治理期 / 回答期两条流程,通用)
 */
import { ArrowDown, ArrowRight, ArrowUp, CornerDownLeft, Lock } from 'lucide-react'
import { type ReactNode } from 'react'

import {
  AUTONOMY,
  EVALUATION,
  GATE,
  JOURNEY,
  REQUEST_PATH,
  ROUTING,
  SHELL_CORE,
  STACK,
  SYSTEM_MAP,
  WORKFLOW,
  WORKFLOW_EXAMPLE,
  WORKFLOW_KIND_LABEL,
  type FlowStep,
  type JourneyStage,
  type RoutingIntent,
  type WorkflowNodeKind,
} from './content'
import { Emphasized, Meta } from './Section'

/* ═════════════════════════ 通用零件 ═════════════════════════ */

/** 步骤之间的箭头。可带一句标签(用在分岔的「未命中」边上) */
function FlowArrow({
  direction = 'down',
  label,
  className = '',
}: {
  direction?: 'down' | 'right'
  label?: string
  className?: string
}) {
  const Icon = direction === 'down' ? ArrowDown : ArrowRight
  return (
    <span
      aria-hidden={label ? undefined : true}
      className={`flex items-center gap-2 ${direction === 'down' ? 'py-1.5' : 'px-1'} ${className}`}
    >
      <Icon className="text-fainter size-4 shrink-0" strokeWidth={1.75} />
      {label && (
        <span className="text-faint text-[12.5px] leading-[1.4]">
          <Emphasized text={label} />
        </span>
      )}
    </span>
  )
}

/** 一张图的题头小标(图内分区用,不占字阶) */
function FigureLabel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={`text-muted-foreground text-[11px] font-semibold tracking-[0.06em] uppercase ${className}`}
    >
      {children}
    </p>
  )
}

/* ═════════════════════════ 总页常驻 ═════════════════════════ */

/** 总页:全局图。左治理期 / 右回答期两条泳道,都落到中间那条「已签字的知识」,
 *  底下一条回边(缺口与投诉回到 01)+ 一条留痕轨。整页唯一的「一眼看懂」入口。 */
export function SystemMapFigure() {
  return (
    <figure className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        {SYSTEM_MAP.lanes.map((lane) => (
          <div
            key={lane.key}
            className="flex flex-col rounded-[18px] border border-[var(--border-strong)] px-5 py-5"
          >
            <FigureLabel>{lane.label}</FigureLabel>
            <p className="text-fainter mt-1 text-[12px]">{lane.who}</p>
            <div className="mt-3.5 flex-1">
              {lane.steps.map((step, i) => (
                <div key={step.name}>
                  <div
                    className={
                      step.gate
                        ? 'border-accent bg-accent-soft rounded-[13px] border-l-[3px] px-4 py-3'
                        : 'bg-subtle rounded-[13px] px-4 py-3'
                    }
                  >
                    <p className="flex flex-wrap items-baseline gap-x-2">
                      <span className="text-fainter font-mono text-[11px]">{`0${i + 1}`}</span>
                      <span className="text-foreground text-[14.5px] leading-[1.35] font-semibold">
                        {step.name}
                      </span>
                      {step.gate && (
                        <span className="bg-card text-accent-ink rounded-[var(--radius-pill)] px-2 py-0.5 text-[10.5px] font-semibold tracking-[0.04em] uppercase">
                          gate
                        </span>
                      )}
                    </p>
                    <p className="text-faint mt-1 text-[12.5px] leading-[1.5]">{step.note}</p>
                  </div>
                  {i < lane.steps.length - 1 && <FlowArrow className="pl-4" />}
                </div>
              ))}
            </div>
            <p className="text-fainter mt-3.5 flex items-center gap-2 text-[12px]">
              {lane.key === 'curation' ? (
                <ArrowDown aria-hidden className="size-3.5 shrink-0" strokeWidth={1.75} />
              ) : (
                <ArrowUp aria-hidden className="size-3.5 shrink-0" strokeWidth={1.75} />
              )}
              {lane.verb}
            </p>
          </div>
        ))}
      </div>

      {/* 知识中枢:两条泳道唯一的交汇点 */}
      <div className="bg-primary-soft rounded-[16px] px-5 py-4">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <p className="text-primary text-[11px] font-semibold tracking-[0.06em] uppercase">
            {SYSTEM_MAP.hubLabel}
          </p>
          <p className="text-secondary-foreground text-[12.5px]">{SYSTEM_MAP.hubNote}</p>
        </div>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {SYSTEM_MAP.hubBlocks.map((block) => (
            <span
              key={block}
              className="bg-card text-secondary-foreground rounded-[10px] px-3 py-1.5 text-[12.5px]"
            >
              {block}
            </span>
          ))}
        </div>
      </div>

      {/* 回边 + 留痕轨 */}
      <div className="border-border-strong flex items-center gap-2.5 rounded-[14px] border border-dashed px-4 py-3">
        <CornerDownLeft aria-hidden className="text-fainter size-4 shrink-0" strokeWidth={1.75} />
        <p className="text-faint text-[12.5px] leading-[1.5]">{SYSTEM_MAP.returnNote}</p>
      </div>
      <div className="bg-subtle flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-[14px] px-4 py-3">
        <FigureLabel>{SYSTEM_MAP.traceLabel}</FigureLabel>
        <p className="text-faint text-[12.5px] leading-[1.5]">{SYSTEM_MAP.traceNote}</p>
      </div>
    </figure>
  )
}

/** 总页:两级路由。**上面三家并排 = 同级**(都事先注册意图,谁命中谁执行),
 *  一条带原因的箭头往下才是兜底的文档检索,再往下是「说没有依据」。
 *  这张图专门用来纠正一个误读:文档 RAG 不是第三级台阶,而是兜底。 */
function IntentBlock({ intent, className = '' }: { intent: RoutingIntent; className?: string }) {
  return (
    <div className={`bg-subtle flex flex-col rounded-[14px] px-4 py-3.5 ${className}`}>
      <span className="flex items-center gap-2.5">
        <span aria-hidden className={`size-2 shrink-0 rounded-full ${intent.dotClass}`} />
        <span className="text-foreground text-[15px] leading-[1.3] font-semibold">
          {intent.label}
        </span>
      </span>
      <span className="text-faint mt-1.5 text-[13px] leading-[1.5]">{intent.note}</span>
      <span className="text-fainter mt-1.5 block text-[12.5px] italic">{intent.example}</span>
    </div>
  )
}

export function RoutingFigure() {
  return (
    <figure className="space-y-1">
      {/* 入口:一句人话的问题 */}
      <div className="border-border-strong rounded-[14px] border px-4 py-3">
        <p className="text-foreground text-[15px] font-semibold">{ROUTING.questionLabel}</p>
        <p className="text-faint mt-1 text-[12.5px] leading-[1.5]">{ROUTING.questionNote}</p>
      </div>
      <FlowArrow className="pl-4" />

      {/* 第一级:三家并排,视觉上必须等宽等高 —— 它们是同级 */}
      <div className="border-border-strong rounded-[18px] border px-5 py-5">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <FigureLabel>{ROUTING.intentLabel}</FigureLabel>
          <p className="text-faint text-[12.5px]">{ROUTING.intentNote}</p>
        </div>
        <div className="mt-3.5 grid items-stretch gap-3 md:grid-cols-3">
          {ROUTING.intents.map((intent) => (
            <IntentBlock key={intent.label} intent={intent} />
          ))}
        </div>
        <p className="text-faint mt-3 text-[12.5px] leading-[1.5]">{ROUTING.peerNote}</p>
      </div>
      <FlowArrow label={ROUTING.missLabel} className="pl-4" />

      {/* 兜底:只有一无所获才走到这里 */}
      <div className="space-y-2">
        <FigureLabel>{ROUTING.fallbackLabel}</FigureLabel>
        <IntentBlock intent={ROUTING.fallback} />
      </div>
      <FlowArrow className="pl-4" />
      <div className="space-y-2">
        <FigureLabel>{ROUTING.lastLabel}</FigureLabel>
        <IntentBlock intent={ROUTING.last} />
      </div>

      <Meta className="flex flex-wrap gap-x-6 gap-y-1 pt-3">
        {ROUTING.axes.map((axis) => (
          <span key={axis}>{axis}</span>
        ))}
      </Meta>
    </figure>
  )
}

/** 三层卡片上的三格计量条:模型自由度(与漏斗 model freedom ↑ 同一口径) */
export function FreedomMeter({ level, dotClass }: { level: number; dotClass: string }) {
  return (
    <span aria-hidden className="flex items-center gap-1">
      {[1, 2, 3].map((i) => (
        <span
          key={i}
          className={`h-1.5 w-5 rounded-full ${i <= level ? dotClass : 'bg-border-strong'}`}
        />
      ))}
    </span>
  )
}

const TONE_DOT: Record<string, string> = {
  neutral: 'bg-border-strong',
  intent: 'bg-border-strong',
  exact: 'bg-kb-exact-qa',
  text2sql: 'bg-kb-text2sql',
  workflow: 'bg-kb-workflow',
  document: 'bg-kb-document',
  none: 'bg-fainter',
}

/** 判定流程图右侧的绿色出口块。意图那一步有三个(三家同级),其余步各一个 */
function ExitBlock({ label, text }: { label?: string; text: string }) {
  return (
    <p className="bg-success-soft text-foreground rounded-[14px] px-4 py-3 text-[13px] leading-[1.5]">
      <span className="text-success mr-1.5 text-[10.5px] font-semibold tracking-[0.04em] uppercase">
        {label ?? 'exit'}
      </span>
      <Emphasized text={text} />
    </p>
  )
}

/** 总页:一次请求的判定流程图。
 *  每一步:方块在左,**命中往右出**(绿块),**未命中沿主干往下**(箭头带原因)。 */
export function RequestPathFigure() {
  return (
    <figure>
      {REQUEST_PATH.steps.map((step, i) => {
        const isLast = i === REQUEST_PATH.steps.length - 1
        return (
          <div key={step.name}>
            <div className="grid items-center gap-2 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,280px)]">
              <div className="bg-subtle rounded-[14px] px-4 py-3.5">
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-fainter font-mono text-[11px]">{`0${i + 1}`}</span>
                  <span
                    aria-hidden
                    className={`mb-[2px] size-[9px] shrink-0 self-center rounded-full ${TONE_DOT[step.tone]}`}
                  />
                  <span className="text-foreground text-[15.5px] leading-[1.3] font-semibold">
                    {step.name}
                  </span>
                </p>
                <p className="text-fainter mt-1 font-mono text-[11px] leading-[1.45]">{step.who}</p>
                <p className="text-secondary-foreground mt-1.5 text-[13.5px] leading-[1.55]">
                  {step.detail}
                </p>
              </div>
              {step.hit || step.exits ? (
                <>
                  <span aria-hidden className="hidden justify-center md:flex">
                    <ArrowRight className="text-fainter size-4" strokeWidth={1.75} />
                  </span>
                  {/* 意图那一步:三个出口并列(同级),命中哪一个就从哪一个出去 */}
                  <div className="space-y-2">
                    {step.exits ? (
                      step.exits.map((exit) => (
                        <ExitBlock key={exit.label} label={exit.label} text={exit.text} />
                      ))
                    ) : (
                      <ExitBlock text={step.hit!} />
                    )}
                  </div>
                </>
              ) : (
                <>
                  <span aria-hidden className="hidden md:block" />
                  <span aria-hidden className="hidden md:block" />
                </>
              )}
            </div>
            {!isLast && <FlowArrow label={step.miss} className="pl-4" />}
          </div>
        )
      })}
      <div className="border-border-soft mt-7 border-t pt-4">
        <FigureLabel>{REQUEST_PATH.tracedLabel}</FigureLabel>
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

/* ═════════════════════════ 总页折叠区 ═════════════════════════ */

/** 折叠区:六层技术架构。自上而下 = 面向用户 → 面向供应商,箭头向上 = 谁支撑谁 */
export function StackFigure() {
  return (
    <figure>
      {STACK.tiers.map((tier, i) => (
        <div key={tier.name}>
          {tier.seam && (
            <div className="border-border-strong my-3 flex items-center gap-3 border-t border-dashed pt-3">
              <Meta>{STACK.seamLabel}</Meta>
            </div>
          )}
          <div className="bg-subtle grid gap-3 rounded-[16px] px-5 py-4 md:grid-cols-[190px_1fr] md:items-center">
            <div>
              <span className="text-fainter font-mono text-[11px]">{`T${STACK.tiers.length - i}`}</span>
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
          {i < STACK.tiers.length - 1 && !STACK.tiers[i + 1].seam && (
            <div className="flex justify-center py-1.5">
              <ArrowUp aria-hidden className="text-fainter size-4" strokeWidth={1.75} />
            </div>
          )}
        </div>
      ))}
      <Meta className="mt-3 flex flex-wrap gap-x-6 gap-y-1">
        {STACK.axis.map((a) => (
          <span key={a}>{a}</span>
        ))}
      </Meta>
    </figure>
  )
}

/** 折叠区:确定性外壳包住有限自主的内核 */
export function ShellCoreFigure() {
  return (
    <figure className="rounded-[18px] border border-[var(--border-strong)] p-5">
      <FigureLabel>{SHELL_CORE.shellLabel}</FigureLabel>
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

/** 折叠区:治理骨架四步(第 3 步是闸门,黄色识别条),步骤之间有箭头 */
export function GateFigure() {
  return (
    <figure className="flex flex-col gap-2 md:flex-row md:items-stretch">
      {GATE.steps.map((step, i) => (
        <div key={step.name} className="flex flex-col gap-2 md:flex-1 md:flex-row md:items-center">
          <div
            className={
              i === 2
                ? 'border-accent bg-accent-soft min-w-0 flex-1 rounded-[16px] border-l-[3px] px-4 py-4'
                : 'bg-subtle min-w-0 flex-1 rounded-[16px] px-4 py-4'
            }
          >
            <span className="text-fainter font-mono text-[11px]">{`0${i + 1}`}</span>
            <p className="text-foreground mt-1 text-[15px] leading-[1.3] font-semibold">
              {step.name}
            </p>
            <p className="text-faint mt-2 text-[13px] leading-[1.6]">{step.keywords}</p>
          </div>
          {i < GATE.steps.length - 1 && (
            <>
              <FlowArrow className="pl-4 md:hidden" />
              <ArrowRight
                aria-hidden
                className="text-fainter hidden size-4 shrink-0 md:block"
                strokeWidth={1.75}
              />
            </>
          )}
        </div>
      ))}
    </figure>
  )
}

const WHO_DOT: Record<string, string> = {
  ops: 'bg-accent',
  user: 'bg-primary',
  system: 'bg-border-strong',
}

/** 折叠区:两个角色的闭环。两段(治理期 / 回答期)各一行,行内箭头相连,末尾一条回边 */
export function JourneyFigure() {
  const phases: JourneyStage['phase'][] = ['curation', 'answer']
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
      {phases.map((phase) => (
        <div key={phase} className="space-y-2">
          <FigureLabel>{JOURNEY.phaseLabels[phase]}</FigureLabel>
          <div className="flex flex-wrap items-stretch gap-2">
            {JOURNEY.stages
              .filter((s) => s.phase === phase)
              .map((stage, i, arr) => {
                const n = JOURNEY.stages.indexOf(stage) + 1
                return (
                  <div key={stage.name} className="flex flex-1 basis-[170px] items-center gap-2">
                    <div className="bg-subtle min-w-0 flex-1 self-stretch rounded-[14px] px-4 py-3.5">
                      <span className="flex items-center gap-2">
                        <span
                          aria-hidden
                          className={`size-2 shrink-0 rounded-full ${WHO_DOT[stage.who]}`}
                        />
                        <span className="text-fainter font-mono text-[11px]">{`0${n}`}</span>
                      </span>
                      <p className="text-foreground mt-1.5 text-[14px] leading-[1.35] font-semibold">
                        {stage.name}
                      </p>
                      <p className="text-faint mt-1 text-[12.5px] leading-[1.5]">{stage.note}</p>
                    </div>
                    {i < arr.length - 1 && (
                      <ArrowRight
                        aria-hidden
                        className="text-fainter size-4 shrink-0"
                        strokeWidth={1.75}
                      />
                    )}
                  </div>
                )
              })}
          </div>
        </div>
      ))}
      <div className="border-border-strong flex items-center gap-2.5 rounded-[14px] border border-dashed px-4 py-3">
        <CornerDownLeft aria-hidden className="text-fainter size-4 shrink-0" strokeWidth={1.75} />
        <p className="text-faint text-[12.5px] leading-[1.5]">{JOURNEY.returnNote}</p>
      </div>
    </figure>
  )
}

/** 折叠区:四层评估。一条自下而上的检查链,每级的检查项做成 chips */
export function EvaluationFigure() {
  return (
    <figure>
      {EVALUATION.levels.map((lvl, i) => (
        <div key={lvl.level}>
          <div className="bg-subtle grid gap-3 rounded-[16px] px-5 py-4 md:grid-cols-[210px_1fr]">
            <div>
              <span className="text-fainter font-mono text-[11px]">{`L${i + 1}`}</span>
              <p className="font-display text-foreground mt-0.5 text-[15px] font-semibold">
                {lvl.level}
              </p>
              <p className="text-faint mt-1 text-[12.5px] leading-[1.5]">{lvl.asks}</p>
            </div>
            <div className="flex flex-wrap content-start gap-2">
              {lvl.checks.map((c) => (
                <span
                  key={c}
                  className="bg-card text-secondary-foreground rounded-[10px] border border-[var(--border-strong)] px-3 py-2 text-[12.5px] leading-[1.35]"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
          {i < EVALUATION.levels.length - 1 && <FlowArrow className="pl-4" />}
        </div>
      ))}
      <Meta className="mt-3 flex flex-wrap gap-x-6 gap-y-1">
        {EVALUATION.axis.map((a) => (
          <span key={a}>{a}</span>
        ))}
      </Meta>
    </figure>
  )
}

/** 折叠区:自主性边界。左宽松 / 右不给,中间一道明确的线 */
export function AutonomyFigure() {
  return (
    <figure className="grid items-stretch gap-4 md:grid-cols-[1fr_auto_1fr]">
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
      <div aria-hidden className="hidden flex-col items-center md:flex">
        <span className="border-border-strong flex-1 border-l border-dashed" />
        <Lock className="text-fainter my-2 size-4 shrink-0" strokeWidth={1.75} />
        <span className="border-border-strong flex-1 border-l border-dashed" />
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

/* ═════════════════ 总页收尾:第四种知识(编排) ═════════════════ */

/** 节点类型的识别色。知识节点用它引用的那一层的色,动作节点用黄色(= 人审闸门) */
const NODE_DOT: Record<WorkflowNodeKind, string> = {
  trigger: 'bg-border-strong',
  llm: 'bg-primary',
  knowledge: 'bg-border-strong',
  compute: 'bg-fainter',
  action: 'bg-accent',
}

/** 节点类型徽标:色点 + mono 短标 */
function NodeBadge({ kind, dotClass }: { kind: WorkflowNodeKind; dotClass?: string }) {
  return (
    <span className="bg-card border-border-strong inline-flex shrink-0 items-center gap-2 rounded-[var(--radius-pill)] border px-2.5 py-1">
      <span
        aria-hidden
        className={`size-[7px] shrink-0 rounded-full ${dotClass ?? NODE_DOT[kind]}`}
      />
      <span className="text-muted-foreground font-mono text-[10.5px] tracking-[0.04em] uppercase">
        {WORKFLOW_KIND_LABEL[kind]}
      </span>
    </span>
  )
}

/** 收尾:编排是什么做的 —— 上面是已签字的知识(只能引用,不能复制),
 *  下面是画布在此之上加的四种节点。方向由中间那条箭头给。 */
export function WorkflowConceptFigure() {
  return (
    <figure className="space-y-1">
      <div className="border-border-strong rounded-[18px] border px-5 py-5">
        <FigureLabel>{WORKFLOW.referencedLabel}</FigureLabel>
        <div className="mt-3 flex flex-wrap gap-2">
          {WORKFLOW.referencedBlocks.map((block) => (
            <span
              key={block.label}
              className="bg-subtle text-secondary-foreground flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px]"
            >
              <span aria-hidden className={`size-2 shrink-0 rounded-full ${block.dotClass}`} />
              {block.label}
            </span>
          ))}
        </div>
      </div>
      <FlowArrow label={WORKFLOW.referencedArrow} className="pl-4" />
      <div className="bg-primary-soft rounded-[18px] px-5 py-5">
        <p className="text-primary text-[11px] font-semibold tracking-[0.06em] uppercase">
          {WORKFLOW.canvasLabel}
        </p>
        <div className="mt-3.5 grid gap-3 md:grid-cols-2">
          {WORKFLOW.kinds.map((kind) => (
            <div key={kind.label} className="bg-card rounded-[14px] px-4 py-3.5">
              <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                <NodeBadge kind={kind.kind} />
                <span className="text-foreground text-[14.5px] leading-[1.3] font-semibold">
                  {kind.label}
                </span>
              </span>
              <p className="text-faint mt-1.5 text-[12.5px] leading-[1.5]">{kind.note}</p>
            </div>
          ))}
        </div>
      </div>
    </figure>
  )
}

/** 收尾:那条客服邮件的编排,逐节点画 input / output / 绑定出去的参数。
 *  最后一个节点是动作节点 —— 打 GATE 徽标,和全站同一个含义:人按下去。 */
export function WorkflowExampleFigure() {
  return (
    <figure>
      {WORKFLOW_EXAMPLE.steps.map((step, i) => (
        <div key={step.name}>
          <div
            className={
              step.gate
                ? 'border-accent bg-accent-soft rounded-[16px] border-l-[3px] px-4 py-3.5'
                : 'bg-subtle rounded-[16px] px-4 py-3.5'
            }
          >
            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
              <span className="text-fainter font-mono text-[11px]">{`0${i + 1}`}</span>
              <NodeBadge kind={step.kind} dotClass={step.source?.dotClass} />
              <span className="text-foreground min-w-0 text-[15px] leading-[1.3] font-semibold">
                {step.name}
              </span>
              {step.source && (
                <span className="text-faint flex items-center gap-2 text-[12px]">
                  <span aria-hidden className={`size-2 rounded-full ${step.source.dotClass}`} />
                  {step.source.label}
                </span>
              )}
              {step.gate && (
                <span className="bg-card text-accent-ink rounded-[var(--radius-pill)] px-2 py-0.5 text-[10.5px] font-semibold tracking-[0.04em] uppercase">
                  gate
                </span>
              )}
            </div>

            <div className="mt-2.5 space-y-1.5">
              {[
                { label: WORKFLOW_EXAMPLE.inLabel, text: step.input },
                { label: WORKFLOW_EXAMPLE.outLabel, text: step.output },
              ].map((row) => (
                <p key={row.label} className="flex gap-2.5">
                  <span className="text-fainter mt-[2px] w-6 shrink-0 font-mono text-[10.5px] tracking-[0.04em] uppercase">
                    {row.label}
                  </span>
                  <span className="text-secondary-foreground min-w-0 text-[13.5px] leading-[1.55]">
                    {row.text}
                  </span>
                </p>
              ))}
            </div>

            {step.binds && (
              <p className="mt-2.5 flex flex-wrap items-center gap-2">
                <span className="text-fainter font-mono text-[10.5px] tracking-[0.04em] uppercase">
                  {WORKFLOW_EXAMPLE.bindsLabel}
                </span>
                {step.binds.map((bind) => (
                  <span
                    key={bind}
                    className="bg-card border-border-strong text-secondary-foreground rounded-[var(--radius-pill)] border border-dashed px-2.5 py-1 text-[12px]"
                  >
                    {bind}
                  </span>
                ))}
              </p>
            )}

            {step.note && (
              <p className="border-border-soft text-faint mt-2.5 border-t pt-2.5 text-[12.5px] leading-[1.5]">
                {step.note}
              </p>
            )}
          </div>
          {i < WORKFLOW_EXAMPLE.steps.length - 1 && <FlowArrow className="pl-4" />}
        </div>
      ))}

      <div className="border-border-soft mt-7 border-t pt-4">
        <FigureLabel>{WORKFLOW_EXAMPLE.traceLabel}</FigureLabel>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {WORKFLOW_EXAMPLE.traced.map((item) => (
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
        <FigureLabel>{label}</FigureLabel>
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
