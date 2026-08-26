/** 编排域的路由壳。
 *
 * 本域目前只有 index 一页(静态设计预览,见 `CanvasPage.tsx`);
 * 真正开发时二级页(画布编辑 / 版本 / 运行记录)在这里往下摆,不碰共享路由表。
 *
 *   /ingest/workflow    编排画布(设计预览,无后端)
 */

import { Route, Routes } from 'react-router-dom'

import { CanvasPage } from './CanvasPage'

export function IngestPage() {
  return (
    <Routes>
      <Route index element={<CanvasPage />} />
    </Routes>
  )
}
