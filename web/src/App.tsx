import { Navigate, Route, Routes } from 'react-router-dom'

import { Toaster } from '@/components/Toaster'
import { DOMAINS } from '@/domains'
import { AppLayout } from '@/layouts/AppLayout'
import { AgentDetailPage } from '@/pages/AgentDetailPage'
import { AgentListPage } from '@/pages/AgentListPage'
import { ChatPage } from '@/pages/ChatPage'
import { JobsPage } from '@/pages/JobsPage'
import { KbListPage } from '@/pages/KbListPage'
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
          <Route path="/kbs" element={<KbListPage />} />
          <Route path="/agents" element={<AgentListPage />} />
          <Route path="/agents/:agentId" element={<AgentDetailPage />} />
          {/* 三个知识域的 ingestion 页由域清单生成(src/domains/index.ts) */}
          {DOMAINS.map((d) => (
            <Route key={d.key} path={d.path} element={<d.IngestPage />} />
          ))}
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/:jobId/review" element={<ReviewPage />} />
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
