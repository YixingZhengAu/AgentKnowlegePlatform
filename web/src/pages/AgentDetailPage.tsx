/** Agent 详情:system prompt + 模型配置 + KB 绑定(按 priority 升序,后端已排好序)。 */

import { ArrowLeft, Bot } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { useApi } from '@/api/hooks'
import type { AgentDetail } from '@/api/schema'
import { DataState } from '@/components/DataState'
import { KbTypeTag } from '@/components/KbTypeTag'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'

export function AgentDetailPage() {
  const { agentId } = useParams()
  const state = useApi<AgentDetail>(`/api/agents/${agentId}`)

  return (
    <div className="flex flex-col gap-6">
      <Link
        to="/agents"
        className="text-muted-foreground hover:text-foreground flex items-center gap-2 text-[12px]"
      >
        <ArrowLeft className="size-4" /> All agents
      </Link>

      <DataState
        state={state}
        emptyIcon={Bot}
        emptyTitle="Agent not found"
        emptyDescription="This agent may have been removed."
      >
        {(agent) => (
          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <div className="flex items-center gap-3">
                  <CardTitle>{agent.name}</CardTitle>
                  <StatusBadge status={agent.status} />
                  <Badge tone="navy">{agent.router_mode}</Badge>
                </div>
                <CardDescription>{agent.description ?? 'No description.'}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <Field label="System prompt">
                  <pre className="bg-muted overflow-x-auto rounded-[var(--radius)] border p-3 font-mono text-[12px] whitespace-pre-wrap">
                    {agent.system_prompt}
                  </pre>
                </Field>
                <Field label="Fallback reply">
                  <p className="text-secondary-foreground text-[12px]">
                    {agent.fallback_reply ?? '—'}
                  </p>
                </Field>
                <Field label="Model config">
                  <pre className="bg-muted overflow-x-auto rounded-[var(--radius)] border p-3 font-mono text-[12px]">
                    {JSON.stringify(agent.model_cfg, null, 2)}
                  </pre>
                </Field>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Bound knowledge bases</CardTitle>
                <CardDescription>
                  Lower priority number wins first. Exact QA is checked before document retrieval,
                  which is checked before analytics.
                </CardDescription>
              </CardHeader>
              <Table>
                <THead>
                  <TR>
                    <TH>Priority</TH>
                    <TH>Knowledge base</TH>
                    <TH>Type</TH>
                    <TH>Top K</TH>
                    <TH>Threshold</TH>
                    <TH>Enabled</TH>
                  </TR>
                </THead>
                <tbody>
                  {agent.bindings.map((b) => (
                    <TR key={b.id}>
                      <TD className="font-mono text-[12px]">{b.priority}</TD>
                      <TD className="font-medium">{b.kb_name}</TD>
                      <TD>
                        <KbTypeTag type={b.kb_type} />
                      </TD>
                      <TD className="font-mono text-[12px]">{b.top_k ?? '—'}</TD>
                      <TD className="font-mono text-[12px]">{b.threshold ?? '—'}</TD>
                      <TD>
                        <StatusBadge status={b.enabled ? 'active' : 'archived'} />
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </Card>
          </div>
        )}
      </DataState>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="text-muted-foreground text-[12px] font-medium">{label}</div>
      {children}
    </div>
  )
}
