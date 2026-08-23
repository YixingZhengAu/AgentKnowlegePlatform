/** 智能问数域的路由壳(S3-PLAN Phase D)。
 *
 * 共享路由表只给每个域一个 `/ingest/<域>/*` 空间(见 `src/App.tsx`),域内二级页在这里摆 ——
 * 于是"本域加一个页面"不需要碰任何共享文件。
 *
 *   /ingest/text2sql                                     数据源管理(D1)
 *   /ingest/text2sql/datasources/:datasourceId/schema     Schema 治理(D2)
 *   /ingest/text2sql/intents                              意图列表 + 空路由负例面(D3)
 *   /ingest/text2sql/intents/:intentId                    意图详情:SQL / 参数区 / 问法(D4)
 *
 * 意图候选的审核走共享路由 `/jobs/:jobId/review`(泛型审核台 + 本域渲染器,D3)。
 */

import { Route, Routes } from 'react-router-dom'

import { DatasourcesPage } from './DatasourcesPage'
import { IntentDetailPage } from './IntentDetailPage'
import { IntentsPage } from './IntentsPage'
import { SchemaPage } from './SchemaPage'

export function IngestPage() {
  return (
    <Routes>
      <Route index element={<DatasourcesPage />} />
      <Route path="datasources/:datasourceId/schema" element={<SchemaPage />} />
      <Route path="intents" element={<IntentsPage />} />
      <Route path="intents/:intentId" element={<IntentDetailPage />} />
    </Routes>
  )
}
