/**
 * 说明页的四张图。
 *
 * 全部用既有 token 的填充块 + flex 画,**不引任何图表库**;文字只放关键词。
 * 倒漏斗用逐层变宽的块宽表达「越往下模型越自由」。
 */
import { ANSWER_FLOW, FUNNEL, GATE, ROLES } from './content'
import { Emphasized, Meta } from './Section'

/** 屏 1:倒漏斗 —— 自上而下四层,块宽递增 */
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

/** 屏 3:治理骨架四步(第 3 步是闸门,黄色识别条) */
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

const TONE_DOT: Record<string, string> = {
  neutral: 'bg-border-strong',
  exact: 'bg-kb-exact-qa',
  text2sql: 'bg-kb-text2sql',
  document: 'bg-kb-document',
  none: 'bg-fainter',
}

/** 屏 4:回答链路 —— 竖向,带连接线,一步一行关键词 */
export function AnswerFlowFigure() {
  return (
    <figure>
      {ANSWER_FLOW.steps.map((step, i) => {
        const isLast = i === ANSWER_FLOW.steps.length - 1
        return (
          <div key={step.name} className="flex gap-4">
            <div className="flex flex-col items-center pt-[8px]">
              <span
                aria-hidden
                className={`size-[9px] shrink-0 rounded-full ${TONE_DOT[step.tone]}`}
              />
              {!isLast && <span aria-hidden className="bg-border w-px flex-1" />}
            </div>
            <div className={isLast ? 'pb-0' : 'pb-5'}>
              <p className="text-foreground text-[16px] font-semibold">{step.name}</p>
              <p className="text-faint mt-0.5 text-[14px] leading-[1.6]">
                <Emphasized text={step.note} />
              </p>
            </div>
          </div>
        )
      })}
    </figure>
  )
}

/** 屏 5:两条泳道 */
export function RolesFigure() {
  return (
    <figure className="grid gap-4 lg:grid-cols-2">
      {ROLES.lanes.map((lane) => (
        <div key={lane.role} className="bg-subtle rounded-[16px] px-5 py-5">
          <p className="text-foreground text-[15px] font-semibold">{lane.role}</p>
          <ol className="mt-3 space-y-2">
            {lane.steps.map((step, i) => (
              <li
                key={step}
                className="text-secondary-foreground flex gap-3 text-[14px] leading-[1.6]"
              >
                <span className="text-fainter mt-px font-mono text-[11px]">{`0${i + 1}`}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
          <p className="border-border-soft text-faint mt-4 border-t pt-3 text-[13px]">
            {lane.note}
          </p>
        </div>
      ))}
    </figure>
  )
}
