/** 静态产物的 URL 拼装 —— 图片与原件 PDF 走 `<img>` / `<iframe>`,不经过 `apiFetch`,
 *  所以前缀要自己带上(开发环境走 Vite 代理时 `API_BASE` 是空串)。
 *
 *  路由出处:`server/app/api/files.py`。 */

import { API_BASE } from '@/api/client'

/** 切片里那张图的 URL。
 *
 * @param documentId 文档 id(在 `origin_ref.document_id` 里)。
 * @param img payload 里的相对路径,形如 `images/<sha256>.jpg`。
 * @returns 可直接放进 `<img src>` 的地址。
 */
export function figureUrl(documentId: string, img: string): string {
  return `${API_BASE}/api/files/parses/${documentId}/${img}`
}

/** 原件 PDF 的 URL,可选跳到某一页。
 *
 * 用浏览器原生阅读器(与 S1 校对页同一个取舍):S2 需要的只是"翻到第 N 页对着看",
 * 不值得为它引 pdf.js。代价是 bbox 高亮做不了。
 *
 * @param documentId 文档 id。
 * @param page 人看的页号(从 1 起);不给就从第一页开始。
 * @returns 带 `#page=N&view=FitH` 片段的地址。
 */
export function documentPdfUrl(documentId: string, page?: number): string {
  const base = `${API_BASE}/api/files/documents/${documentId}/pdf`
  return page ? `${base}#page=${page}&view=FitH` : base
}
