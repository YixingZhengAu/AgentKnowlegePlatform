/** Agent 列表:点一行进详情(详情页要用嵌套类型 AgentDetailOut.bindings)。 */

import { Bot } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { useApi } from '@/api/hooks'
import type { AgentList } from '@/api/schema'
import { DataState } from '@/components/DataState'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { fmtDate } from '@/lib/format'

export function AgentListPage() {
  const state = useApi<AgentList>('/api/agents')
  const navigate = useNavigate()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configured agents</CardTitle>
        <CardDescription>
          An agent binds knowledge bases in priority order and decides where each question should be
          answered from.
        </CardDescription>
      </CardHeader>
      <DataState
        state={state}
        isEmpty={(d) => d.items.length === 0}
        emptyIcon={Bot}
        emptyTitle="No agents yet"
        emptyDescription="Run `make seed` to create the default assistant."
      >
        {(data) => (
          <Table>
            <THead>
              <TR>
                <TH>Name</TH>
                <TH>Description</TH>
                <TH>Router</TH>
                <TH>Status</TH>
                <TH>Created</TH>
              </TR>
            </THead>
            <tbody>
              {data.items.map((agent) => (
                <TR
                  key={agent.id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/agents/${agent.id}`)}
                >
                  <TD className="font-medium">{agent.name}</TD>
                  <TD className="text-secondary-foreground max-w-[420px] text-[12px]">
                    {agent.description ?? '—'}
                  </TD>
                  <TD>
                    <Badge tone="navy">{agent.router_mode}</Badge>
                  </TD>
                  <TD>
                    <StatusBadge status={agent.status} />
                  </TD>
                  <TD className="text-muted-foreground text-[12px]">{fmtDate(agent.created_at)}</TD>
                </TR>
              ))}
            </tbody>
          </Table>
        )}
      </DataState>
    </Card>
  )
}
