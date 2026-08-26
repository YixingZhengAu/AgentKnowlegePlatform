/** 文档 RAG 域描述符 —— 本域对外暴露的全部信息(路由 / 导航 / 识别色 / 审核渲染器)。 */

import { FileText } from 'lucide-react'

import type { DomainModule } from '../types'
import { chunkActions } from './actions'
import { ChunkCitation } from './Citation'
import { IngestPage } from './IngestPage'
import { ChunkItemCard, ChunkItemEditor, ChunkOriginPanel } from './renderers'

export const documentDomain: DomainModule = {
  key: 'document',
  label: 'Document RAG',
  path: '/ingest/document',
  icon: FileText,
  toneClass: 'bg-kb-document',
  IngestPage,
  renderers: {
    // item_type 取值见 server/app/models/ingest.py 的 ITEM_TYPES
    chunk: {
      label: 'Document chunk',
      card: ChunkItemCard,
      editor: ChunkItemEditor,
      origin: ChunkOriginPanel,
      // 左原文右编辑并排(可收起):审切片要原文和结果同屏对照(S2-PLAN 附录三 F2)
      originPlacement: 'side',
      // 保留 S0 泛型语义(标 approved → 批量发布),只换文案与驳回纪律(见 actions.ts)
      actions: chunkActions,
    },
  },
  citations: {
    // citation_type 由后端 `_doc_rag_citations()` 写死成 "chunk"
    chunk: ChunkCitation,
  },
}
