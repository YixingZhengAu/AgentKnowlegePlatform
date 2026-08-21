/** 知识库列表:纯只读,消费 GET /api/kbs —— 证明"后端 -> openapi -> 前端类型"是通的。 */

import { Library } from 'lucide-react'

import { useApi } from '@/api/hooks'
import type { KbList } from '@/api/schema'
import { DataState } from '@/components/DataState'
import { KbTypeTag } from '@/components/KbTypeTag'
import { StatusBadge } from '@/components/StatusBadge'
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { fmtDate } from '@/lib/format'

export function KbListPage() {
  const state = useApi<KbList>('/api/kbs')

  return (
    <Card>
      <CardHeader>
        <CardTitle>Governance tiers</CardTitle>
        <CardDescription>
          Three governance tiers, one per error tolerance level: exact answers, document retrieval
          and analytics over the business database.
        </CardDescription>
      </CardHeader>
      <DataState
        state={state}
        isEmpty={(d) => d.items.length === 0}
        emptyIcon={Library}
        emptyTitle="No knowledge bases yet"
        emptyDescription="Run `make seed` to create the three demo knowledge bases."
      >
        {(data) => (
          <Table>
            <THead>
              <TR>
                <TH>Name</TH>
                <TH>Type</TH>
                <TH>Description</TH>
                <TH>Status</TH>
                <TH>Created</TH>
              </TR>
            </THead>
            <tbody>
              {data.items.map((kb) => (
                <TR key={kb.id}>
                  <TD className="font-medium">{kb.name}</TD>
                  <TD>
                    <KbTypeTag type={kb.type} />
                  </TD>
                  <TD className="text-secondary-foreground max-w-[420px] text-[12px]">
                    {kb.description ?? '—'}
                  </TD>
                  <TD>
                    <StatusBadge status={kb.status} />
                  </TD>
                  <TD className="text-muted-foreground text-[12px]">{fmtDate(kb.created_at)}</TD>
                </TR>
              ))}
            </tbody>
          </Table>
        )}
      </DataState>
    </Card>
  )
}
