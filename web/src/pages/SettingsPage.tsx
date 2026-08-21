/** 设置页(只读):消费 /healthz —— 演示时用来证明"库通不通、维度是多少"一眼可见。
 *
 * 注意:任何密钥都不进前端。这里显示的只有环境名、DB 连通性与向量维度。
 */

import { Activity } from 'lucide-react'

import { useApi } from '@/api/hooks'
import type { Health } from '@/api/schema'
import { DataState } from '@/components/DataState'
import { StatusBadge } from '@/components/StatusBadge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function SettingsPage() {
  const state = useApi<Health>('/healthz')

  return (
    <div className="flex max-w-[720px] flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>System health</CardTitle>
          <CardDescription>
            Live check of the API process, its database connection and the embedding dimension the
            vector columns were built with.
          </CardDescription>
        </CardHeader>
        <DataState
          state={state}
          emptyIcon={Activity}
          emptyTitle="Health check unavailable"
          emptyDescription="The API server did not answer."
        >
          {(health) => (
            <CardContent className="flex flex-col gap-3">
              <Row label="API">
                <StatusBadge status={health.status === 'ok' ? 'ok' : 'failed'} />
              </Row>
              <Row label="Environment">
                <span className="font-mono text-[12px]">{health.env}</span>
              </Row>
              <Row label="Database">
                <span className="font-mono text-[12px]">{health.database}</span>
              </Row>
              <Row label="Embedding dimension">
                <span className="font-mono text-[12px]">{health.embedding_dim}</span>
              </Row>
              {health.database_error && (
                <Row label="Database error">
                  <span className="text-destructive font-mono text-[12px]">
                    {health.database_error}
                  </span>
                </Row>
              )}
            </CardContent>
          )}
        </DataState>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
          <CardDescription>
            Models, keys and connection strings live in the server environment only. Nothing
            sensitive is exposed to the browser.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-secondary-foreground flex flex-col gap-2 text-[12px]">
          <p>
            The application asks for a <span className="font-mono">main</span> or{' '}
            <span className="font-mono">light</span> model tier and never names a model, so
            switching models is a configuration change rather than a code change.
          </p>
          <p>
            Changing the embedding dimension rebuilds the vector columns, so it is a migration, not
            a setting.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b pb-2 last:border-0 last:pb-0">
      <span className="text-muted-foreground text-[12px]">{label}</span>
      {children}
    </div>
  )
}
