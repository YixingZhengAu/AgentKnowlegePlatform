import { Navigate, Route, Routes } from 'react-router-dom'

import { Toaster } from '@/components/Toaster'
import { DOMAINS } from '@/domains'
import { AppLayout } from '@/layouts/AppLayout'
import { AgentDetailPage } from '@/pages/AgentDetailPage'
import { AgentListPage } from '@/pages/AgentListPage'
import { ChatPage } from '@/pages/ChatPage'
import { LayerPage, OverviewPage, WorkflowPage } from '@/pages/how-it-works'
import { ReviewPage } from '@/pages/ReviewPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { StyleGuidePage } from '@/pages/StyleGuidePage'

export default function App() {
  return (
    <>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/agents" element={<AgentListPage />} />
          <Route path="/agents/:agentId" element={<AgentDetailPage />} />
          {/* 各知识域的 ingestion 页由域清单生成(src/domains/index.ts;含只有设计预览的 workflow)。
              `/*` 是给域自己开的子路由空间:S1 的校对页这类"域内二级页"由该域的
              IngestPage 内部再摆一层 <Routes>,共享路由表不认识任何具体域的子页 */}
          {DOMAINS.map((d) => (
            <Route key={d.key} path={`${d.path}/*`} element={<d.IngestPage />} />
          ))}
          <Route path="/jobs/:jobId/review" element={<ReviewPage />} />
          {/* 项目说明页(投屏讲稿):总页 + 架构页 + 三个知识层的子页,零后端依赖。
              架构页必须排在 `/:layer` 之前,否则会被当成未知 slug 重定向回总页 */}
          <Route path="/how-it-works" element={<OverviewPage />} />
          {/* 编排那一页在 :layer 之前显式声明 —— 它不是 LayerSlug,走自己的页面 */}
          <Route path="/how-it-works/workflow" element={<WorkflowPage />} />
          <Route path="/how-it-works/:layer" element={<LayerPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          {/* 隐藏路由:UI 验收对照页,不进侧栏 */}
          <Route path="/styleguide" element={<StyleGuidePage />} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>
      <Toaster />
    </>
  )
}
