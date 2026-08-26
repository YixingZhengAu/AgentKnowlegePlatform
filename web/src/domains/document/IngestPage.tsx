/** 文档 RAG 域的路由壳。
 *
 * 共享路由表只给每个域一个 `/ingest/<域>/*` 空间(见 `src/App.tsx`),域内二级页在这里摆 ——
 * 于是"本域加一个页面"不需要碰任何共享文件。
 *
 *   /ingest/document                    文档列表 + 上传
 *   /ingest/document/search             检索调试台(两条腿 / RRF / 重排,S2-4)
 *   /ingest/document/documents/:id/chunks  切片管理页(已发布的正式行,S2-4)
 *
 * 切片**审核**走共享路由 `/jobs/:jobId/review`(泛型审核台 + 本域注册的渲染器与动作),
 * 没有"先校对解析文本"那一关 —— 文档 RAG 审的是切片本身。
 * 🩸 审核页(发布前,`staging_items`)与管理页(发布后,`chunks`)是两个不同的页面,
 * 别把它们的动作搞混:不采纳 ≠ 禁用。
 */

import { Route, Routes } from 'react-router-dom'

import { ChunksPage } from './ChunksPage'
import { DocumentsPage } from './DocumentsPage'
import { SearchConsolePage } from './SearchConsolePage'

export function IngestPage() {
  return (
    <Routes>
      <Route index element={<DocumentsPage />} />
      <Route path="search" element={<SearchConsolePage />} />
      <Route path="documents/:documentId/chunks" element={<ChunksPage />} />
    </Routes>
  )
}
