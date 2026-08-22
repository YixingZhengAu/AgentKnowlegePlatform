/** 精准 QA 域的路由壳(S1-plan Step 7)。
 *
 * 共享路由表只给每个域一个 `/ingest/<域>/*` 空间(见 `src/App.tsx`),域内二级页在这里摆 ——
 * 于是"本域加一个页面"不需要碰任何共享文件。
 *
 *   /ingest/exact-qa                                  文档列表 + 上传 + 已发布问答库
 *   /ingest/exact-qa/documents/:documentId/proofread   解析校对页(第一道人工关)
 *
 * 候选审核台走共享路由 `/jobs/:jobId/review`(泛型审核台 + 本域注册的渲染器与动作)。
 */

import { Route, Routes } from 'react-router-dom'

import { DocumentsPage } from './DocumentsPage'
import { ProofreadPage } from './ProofreadPage'

export function IngestPage() {
  return (
    <Routes>
      <Route index element={<DocumentsPage />} />
      <Route path="documents/:documentId/proofread" element={<ProofreadPage />} />
    </Routes>
  )
}
