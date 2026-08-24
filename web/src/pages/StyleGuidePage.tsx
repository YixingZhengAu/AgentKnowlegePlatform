/** /styleguide —— UI 验收对照页(S0-PLAN Step 6 + UI-STYLE §5.4)。
 *
 * 隐藏路由,不进侧栏导航。平铺全部 token 与组件态,改风格后一眼能看出哪里变了。
 * 色值不写死:直接从 CSS 变量读回来显示 —— 于是"hex 只出现在 token 定义处"这条纪律
 * 在这一页也成立(这页只是照镜子,不是第二份色表)。
 */

import { Inbox } from 'lucide-react'
import { useMemo } from 'react'

import { EmptyState } from '@/components/EmptyState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { pushToast } from '@/lib/toast'

const BRAND = [
  '--brand-navy',
  '--brand-navy-hover',
  '--brand-navy-soft',
  '--brand-yellow',
  '--brand-yellow-soft',
  '--brand-dark',
  '--brand-ink',
  '--brand-ink-soft',
  '--brand-ink-muted',
  '--brand-ink-faint',
  '--brand-ink-fainter',
  '--brand-nav',
  '--brand-fill',
  '--brand-fill-strong',
  '--brand-line-strong',
  '--brand-line',
  '--brand-line-soft',
  '--brand-sel',
  '--brand-green',
  '--brand-amber',
  '--brand-red',
  '--brand-blue',
]

const SEMANTIC = [
  '--background',
  '--foreground',
  '--card',
  '--primary',
  '--primary-hover',
  '--primary-soft',
  '--accent',
  '--accent-soft',
  '--secondary-foreground',
  '--muted',
  '--muted-foreground',
  '--faint',
  '--subtle',
  '--border-strong',
  '--border',
  '--border-soft',
  '--selected',
  '--ring',
  '--success',
  '--warning',
  '--destructive',
  '--info',
]

const KB = ['--kb-exact-qa', '--kb-document', '--kb-text2sql']

/** 读回 :root 上的变量真值(只用于显示,着色一律走 var())。 */
function useResolvedVars(names: string[]) {
  return useMemo(() => {
    const style = getComputedStyle(document.documentElement)
    const map: Record<string, string> = {}
    for (const n of names) map[n] = style.getPropertyValue(n).trim()
    return map
  }, [names])
}

function Swatches({ names }: { names: string[] }) {
  const resolved = useResolvedVars(names)
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      {names.map((n) => (
        <div key={n} className="flex items-center gap-3">
          <div
            className="size-9 shrink-0 rounded-[var(--radius)] border border-[var(--border-strong)]"
            style={{ background: `var(${n})` }}
          />
          <div className="min-w-0">
            <div className="truncate font-mono text-[11.5px] font-medium">{n}</div>
            <div className="text-faint font-mono text-[11px]">{resolved[n] ?? '…'}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function Section({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="flex flex-col gap-5">{children}</CardContent>
    </Card>
  )
}

export function StyleGuidePage() {
  return (
    <div className="flex max-w-[900px] flex-col gap-6">
      <Section
        title="Brand palette"
        description="Raw brand values. This is the only layer that holds literal colours."
      >
        <Swatches names={BRAND} />
      </Section>

      <Section
        title="Semantic tokens"
        description="What components actually reference. Renaming a brand colour never touches a component."
      >
        <Swatches names={SEMANTIC} />
      </Section>

      <Section
        title="Knowledge tier colours"
        description="Fixed across the whole product: exact QA is yellow, document retrieval is blue, analytics is violet."
      >
        <Swatches names={KB} />
      </Section>

      <Section
        title="Typography"
        description="Display font for headings and navigation, body font for prose, monospace for traces and SQL."
      >
        <div className="flex flex-col gap-2">
          <div className="font-display text-[19px] font-bold tracking-[-0.01em]">
            Page title · 19 / 700
          </div>
          <div className="font-display text-[15px] font-bold">Card title · 15 / 700</div>
          <div className="text-[14px]">Body copy · 14 / 400 — the working size for everything.</div>
          <div className="text-faint text-[11.5px]">Support text · 11.5 / 400</div>
          <div className="text-faint font-mono text-[12px]">
            retrieve_exact_qa · 812 ms · 1,204 tokens
          </div>
        </div>
      </Section>

      <Section title="Buttons" description="All pills. One navy solid button per screen at most.">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Primary</Button>
          <Button variant="accent">Publish</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="danger">Delete</Button>
          <Button variant="ghost">Ghost</Button>
          <Button disabled>Disabled</Button>
          <Button size="sm">Small</Button>
        </div>
      </Section>

      <Section title="Badges" description="Every tone is a foreground paired with its own soft ground.">
        <div className="flex flex-wrap items-center gap-3">
          <Badge>neutral</Badge>
          <Badge tone="navy">navy</Badge>
          <Badge tone="accent">exact hit</Badge>
          <Badge tone="success">approved</Badge>
          <Badge tone="warning">to review</Badge>
          <Badge tone="danger">rejected</Badge>
          <Badge tone="info">edited</Badge>
        </div>
      </Section>

      <Section
        title="Radius and elevation"
        description="Controls are pills, containers round at 18px, five shadow steps."
      >
        <div className="flex flex-wrap items-center gap-4">
          <div className="bg-subtle text-faint flex size-24 items-center justify-center rounded-[var(--radius)] font-mono text-[11px]">
            input
          </div>
          <div className="bg-card text-faint flex size-24 items-center justify-center rounded-[var(--radius-row)] border border-[var(--border)] font-mono text-[11px]">
            row
          </div>
          <div className="bg-card text-faint flex size-24 items-center justify-center rounded-[var(--radius-card)] border border-[var(--border)] font-mono text-[11px] shadow-[var(--shadow-card)]">
            card
          </div>
          <div className="bg-card text-faint flex size-24 items-center justify-center rounded-[var(--radius-card)] border border-[var(--border)] font-mono text-[11px] shadow-[var(--shadow-pop)]">
            popover
          </div>
        </div>
      </Section>

      <Section title="Form controls">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-[12.5px] font-semibold">Knowledge base name</label>
            <Input placeholder="Residential inverter FAQ" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-faint text-[12.5px] font-semibold">Disabled</label>
            <Input placeholder="Read only" disabled />
          </div>
        </div>
      </Section>

      <Section title="Table" description="Label-style header, hover row, no zebra striping.">
        <Table>
          <THead>
            <TR>
              <TH>Stage</TH>
              <TH>Status</TH>
              <TH>Latency</TH>
            </TR>
          </THead>
          <tbody>
            <TR>
              <TD className="font-mono text-[12px]">retrieve_exact_qa</TD>
              <TD>
                <Badge tone="success">ok</Badge>
              </TD>
              <TD className="text-faint font-mono text-[12px]">812 ms</TD>
            </TR>
            <TR>
              <TD className="font-mono text-[12px]">generate</TD>
              <TD>
                <Badge tone="danger">error</Badge>
              </TD>
              <TD className="text-faint font-mono text-[12px]">4.81 s</TD>
            </TR>
          </tbody>
        </Table>
      </Section>

      <Section title="Loading and empty states">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-2/3" />
        </div>
        <EmptyState
          icon={Inbox}
          title="Nothing to review"
          description="Approved items move straight to publishing."
          action={
            <Button variant="secondary" size="sm">
              Import documents
            </Button>
          }
        />
      </Section>

      <Section
        title="Toasts"
        description="Errors surface here with the backend error code, so a screenshot is enough to debug."
      >
        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => pushToast('error', 'db_error', 'The database is not reachable.')}
          >
            Error toast
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => pushToast('info', 'job_queued', 'Extraction job accepted.')}
          >
            Info toast
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => pushToast('success', 'published', '12 QA pairs published.')}
          >
            Success toast
          </Button>
        </div>
      </Section>
    </div>
  )
}
