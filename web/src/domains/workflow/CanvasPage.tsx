/** 编排域首页 —— **静态设计预览,没有后端**(2026-08-27 需求方定:先留空,不开发)。
 *
 * 页面存在的理由只有一个:让来看演示的人一眼明白「第四种知识长什么样、放在哪」。
 * 所以它长成一个编排画布该有的样子(左侧节点面板 / 中间画布 / 右侧节点检查器),
 * 但**任何东西都不可交互、不落库、不发请求** —— 页顶那条横幅必须一直说清这件事。
 *
 * 说明性文字与真正的例子在说明页(`/how-it-works#workflows`),这里不重复讲道理,
 * 只把形状摆出来;两处的节点顺序保持一致,别让人以为是两个东西。
 * 域纪律:不 import 兄弟域,识别色只用 `bg-kb-workflow`(色值在 index.css)。
 */

import { ArrowRight, ChevronDown, Info, Lock, Maximize2, Minus, Plus, Workflow } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

/** 左侧面板:能拖到画布上的节点种类(与说明页的四种节点同一口径 + 触发器) */
const PALETTE = [
  { label: 'Trigger', note: 'email · schedule · a question', dot: 'bg-border-strong' },
  { label: 'Knowledge', note: 'call an approved layer', dot: 'bg-kb-workflow' },
  { label: 'LLM', note: 'judge · classify · write', dot: 'bg-primary' },
  { label: 'Code', note: 'branch · threshold · maths', dot: 'bg-fainter' },
  { label: 'Action', note: 'log · update · notify', dot: 'bg-accent' },
]

/** 画布上的节点(= 说明页那条客服邮件编排,标签压到一行) */
const NODES = [
  { kind: 'Trigger', name: 'New support email', meta: 'inbox: support@', dot: 'bg-border-strong' },
  {
    kind: 'LLM',
    name: 'Read intent & mood',
    meta: 'binds: order number · mood',
    dot: 'bg-primary',
  },
  {
    kind: 'Knowledge',
    name: 'Order status & delay',
    meta: 'Text-to-SQL · signed definition',
    dot: 'bg-kb-text2sql',
    selected: true,
  },
  { kind: 'Code', name: 'Which delay band?', meta: 'binds: band', dot: 'bg-fainter' },
  {
    kind: 'Knowledge',
    name: 'Approved handling',
    meta: 'Exact Q&A · verbatim',
    dot: 'bg-kb-exact-qa',
  },
  {
    kind: 'Knowledge',
    name: 'Reply template',
    meta: 'Exact Q&A · verbatim',
    dot: 'bg-kb-exact-qa',
  },
  {
    kind: 'LLM',
    name: 'Draft the reply',
    meta: 'tone only — promises are quoted',
    dot: 'bg-primary',
  },
  {
    kind: 'Action',
    name: 'Log & update record',
    meta: 'waits for a human',
    dot: 'bg-accent',
    gate: true,
  },
]

/** 右侧检查器:选中的那个知识节点。参数是 AI 自动认出来的,不用手接线 */
const INSPECTOR = {
  node: 'Order status & delay',
  kind: 'Knowledge node',
  source: 'Text-to-SQL · a definition the business signed',
  inputs: [{ name: 'order number', from: 'auto-bound from step 02' }],
  outputs: ['status', 'promised date', 'revised date', 'days late'],
  guard: 'Read-only. No free-form SQL — the node fills the parameters of a published definition.',
}

export function CanvasPage() {
  return (
    <div className="mx-auto max-w-[1180px] space-y-5 px-6 py-6">
      {/* 横幅:这一页是设计预览,不是功能 */}
      <Card className="flex flex-wrap items-start gap-3 px-[26px] py-4">
        <Info className="text-fainter mt-[2px] size-4 shrink-0" strokeWidth={1.75} />
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-display text-[15px] font-bold tracking-[-0.01em]">
            Design preview — nothing here is wired up
          </p>
          <p className="text-faint text-[12.5px] leading-[1.6]">
            Workflows are the fourth kind of knowledge: they compose the other three instead of
            adding new facts. The three they compose are running today; this canvas is the next
            slice, so this page saves nothing and calls nothing.
          </p>
        </div>
        <Link to="/how-it-works#workflows">
          <Button variant="secondary" size="sm">
            Read the design
            <ArrowRight strokeWidth={1.75} />
          </Button>
        </Link>
      </Card>

      <Card className="overflow-hidden">
        {/* 工具条:摆出编排器该有的样子,全部禁用 */}
        <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border-soft)] px-[26px] py-3.5">
          <Workflow className="text-fainter size-4 shrink-0" strokeWidth={1.75} />
          <p className="font-display text-[15px] font-bold tracking-[-0.01em]">
            Late order · customer reply
          </p>
          <Badge tone="neutral">draft</Badge>
          <span className="text-fainter text-[12px]">8 nodes · 3 knowledge layers · 1 gate</span>
          <span className="ml-auto flex items-center gap-2">
            <Button variant="secondary" size="sm" disabled>
              Test run
            </Button>
            <Button size="sm" disabled>
              Publish
            </Button>
          </span>
        </div>

        <div className="grid lg:grid-cols-[190px_minmax(0,1fr)_270px]">
          {/* 左:节点面板 */}
          <div className="space-y-2.5 border-b border-[var(--border-soft)] px-5 py-5 lg:border-r lg:border-b-0">
            <p className="text-muted-foreground text-[11px] font-semibold tracking-[0.06em] uppercase">
              Nodes
            </p>
            {PALETTE.map((item) => (
              <div key={item.label} className="bg-subtle rounded-[12px] px-3 py-2.5">
                <p className="flex items-center gap-2.5">
                  <span aria-hidden className={`size-2 shrink-0 rounded-full ${item.dot}`} />
                  <span className="text-foreground text-[13px] font-semibold">{item.label}</span>
                </p>
                <p className="text-fainter mt-0.5 pl-[18px] text-[11.5px] leading-[1.45]">
                  {item.note}
                </p>
              </div>
            ))}
          </div>

          {/* 中:画布。点阵底纹用 token 色值画,不引新 hex */}
          <div
            className="relative border-b border-[var(--border-soft)] px-6 py-6 lg:border-b-0"
            style={{
              backgroundImage: 'radial-gradient(var(--border-strong) 1px, transparent 0)',
              backgroundSize: '18px 18px',
            }}
          >
            <div className="flex flex-col items-center">
              {NODES.map((node, i) => (
                <div key={node.name} className="flex w-full max-w-[380px] flex-col items-center">
                  <div
                    className={`bg-card w-full rounded-[14px] border px-4 py-3 shadow-[var(--shadow-card)] ${
                      node.selected
                        ? 'border-[var(--ring)]'
                        : node.gate
                          ? 'border-accent'
                          : 'border-[var(--border-strong)]'
                    }`}
                  >
                    <p className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                      <span aria-hidden className={`size-2 shrink-0 rounded-full ${node.dot}`} />
                      <span className="text-muted-foreground font-mono text-[10.5px] tracking-[0.04em] uppercase">
                        {node.kind}
                      </span>
                      <span className="text-foreground text-[13.5px] font-semibold">
                        {node.name}
                      </span>
                      {node.gate && (
                        <Lock className="text-accent-ink size-3.5" strokeWidth={1.75} />
                      )}
                    </p>
                    <p className="text-fainter mt-1 pl-[18px] text-[11.5px] leading-[1.45]">
                      {node.meta}
                    </p>
                  </div>
                  {/* 连线:点阵底上细线几乎看不见,所以用一个小箭头收口 */}
                  {i < NODES.length - 1 && (
                    <span aria-hidden className="text-fainter flex flex-col items-center py-1">
                      <ChevronDown className="size-4" strokeWidth={1.75} />
                    </span>
                  )}
                </div>
              ))}
            </div>

            {/* 缩放控件:静态,只为形状 */}
            <span
              aria-hidden
              className="bg-card border-border-strong text-fainter absolute right-4 bottom-4 flex items-center gap-2 rounded-[var(--radius-pill)] border px-2.5 py-1.5"
            >
              <Minus className="size-3.5" strokeWidth={1.75} />
              <span className="font-mono text-[11px]">100%</span>
              <Plus className="size-3.5" strokeWidth={1.75} />
              <Maximize2 className="size-3.5" strokeWidth={1.75} />
            </span>
          </div>

          {/* 右:节点检查器 */}
          <div className="space-y-4 px-5 py-5 lg:border-l lg:border-[var(--border-soft)]">
            <div>
              <p className="text-muted-foreground text-[11px] font-semibold tracking-[0.06em] uppercase">
                {INSPECTOR.kind}
              </p>
              <p className="font-display mt-1 text-[14px] font-bold tracking-[-0.01em]">
                {INSPECTOR.node}
              </p>
              <p className="text-faint mt-1 text-[12px] leading-[1.5]">{INSPECTOR.source}</p>
            </div>

            <div>
              <p className="text-fainter font-mono text-[10.5px] tracking-[0.06em] uppercase">
                Inputs
              </p>
              <div className="mt-2 space-y-2">
                {INSPECTOR.inputs.map((input) => (
                  <div
                    key={input.name}
                    className="border-border-strong rounded-[10px] border border-dashed px-3 py-2"
                  >
                    <p className="text-foreground text-[12.5px] font-semibold">{input.name}</p>
                    <p className="text-fainter mt-0.5 text-[11.5px]">{input.from}</p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="text-fainter font-mono text-[10.5px] tracking-[0.06em] uppercase">
                Outputs
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {INSPECTOR.outputs.map((out) => (
                  <span
                    key={out}
                    className="bg-subtle text-secondary-foreground rounded-[var(--radius-pill)] px-2.5 py-1 text-[11.5px]"
                  >
                    {out}
                  </span>
                ))}
              </div>
            </div>

            <p className="bg-subtle text-faint rounded-[12px] px-3 py-2.5 text-[11.5px] leading-[1.55]">
              {INSPECTOR.guard}
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}
