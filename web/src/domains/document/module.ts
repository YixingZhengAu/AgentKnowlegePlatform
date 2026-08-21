/** 文档 RAG 域描述符。暂无审核渲染器(chunk 类型走 JSON 兜底),由本域开发者补齐。 */

import { FileText } from 'lucide-react'

import type { DomainModule } from '../types'
import { IngestPage } from './IngestPage'

export const documentDomain: DomainModule = {
  key: 'document',
  label: 'Document RAG',
  path: '/ingest/document',
  icon: FileText,
  toneClass: 'bg-kb-document',
  IngestPage,
}
