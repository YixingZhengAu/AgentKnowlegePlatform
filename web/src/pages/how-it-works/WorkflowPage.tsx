/**
 * `/how-it-works/workflow` 子页:第四种知识 —— 编排。
 * 和三层子页同级地挂在侧栏(顺序里排在文档兜底之前),内容由总页收尾那一节整体搬来:
 *   概念图(引用已审知识 → 画布上的四类节点)→ 四条纪律 W1–W4 →
 *   「已设计、未落地」状态条 → 那条客服邮件的逐节点例子 → 一句收口。
 * 纪律:它必须自己说清「已设计、未落地」,动作节点仍守 AUTONOMY 那条线。
 * 只渲染 content.ts 的数据;字阶走 Section.tsx。
 */
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

import { BACK_TO_OVERVIEW, WORKFLOW, WORKFLOW_CARD, WORKFLOW_EXAMPLE } from './content'
import { WorkflowConceptFigure, WorkflowExampleFigure } from './figures'
import { Emphasis, Lede, Meta, Screen, ScreenTitle, SectionHeading } from './Section'

export function WorkflowPage() {
  return (
    <div className="mx-auto max-w-[860px] space-y-12 pt-6 pb-28">
      <Link
        to="/how-it-works"
        className="text-secondary-foreground hover:text-primary inline-flex items-center gap-1.5 text-[12.5px] font-semibold transition-colors duration-150"
      >
        <ArrowLeft className="size-3.5" strokeWidth={1.75} />
        {BACK_TO_OVERVIEW}
      </Link>

      {/* 页头:识别色 + 标题 + 主角句 + 例子 chips(和三层子页一个形状) */}
      <Screen className="space-y-5">
        <div className="flex items-center gap-3">
          <span aria-hidden className={`size-2.5 rounded-full ${WORKFLOW_CARD.dotClass}`} />
          <ScreenTitle>{WORKFLOW.title}</ScreenTitle>
        </div>
        <Lede text={WORKFLOW.lede} />
        <div className="flex flex-wrap gap-2">
          {WORKFLOW_CARD.examples.map((ex) => (
            <span
              key={ex}
              className="text-secondary-foreground rounded-[var(--radius-pill)] border border-[var(--border-strong)] px-3.5 py-1.5 text-[12.5px] font-medium"
            >
              {ex}
            </span>
          ))}
        </div>
      </Screen>

      {/* 它由什么组成:引用已审知识 → 画布上的四类节点 */}
      <Screen className="space-y-3">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <SectionHeading>{WORKFLOW.builtFromLabel}</SectionHeading>
          <Meta>{WORKFLOW.summary}</Meta>
        </div>
        <p className="text-secondary-foreground text-[15px] leading-[1.6]">
          {WORKFLOW.builtFromNote}
        </p>
        <WorkflowConceptFigure />
      </Screen>

      {/* 四条纪律 */}
      <Screen>
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
      </Screen>

      {/* 已设计、未落地 */}
      <Screen>
        <p className="border-border-strong flex flex-wrap items-baseline gap-x-2.5 rounded-[14px] border border-dashed px-4 py-3">
          <span className="text-muted-foreground font-mono text-[10.5px] tracking-[0.06em] uppercase">
            {WORKFLOW.statusLabel}
          </span>
          <span className="text-faint text-[13px] leading-[1.55]">{WORKFLOW.status}</span>
        </p>
      </Screen>

      {/* 逐节点的例子:每步的知识来源 + 输入输出 + 自动识别到的参数 */}
      <Screen className="space-y-3">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <SectionHeading>{WORKFLOW_EXAMPLE.title}</SectionHeading>
          <Meta>{WORKFLOW_EXAMPLE.summary}</Meta>
        </div>
        <Meta>{WORKFLOW_EXAMPLE.scenario}</Meta>
        <WorkflowExampleFigure />
        <Emphasis text={WORKFLOW_EXAMPLE.emphasis} />
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
