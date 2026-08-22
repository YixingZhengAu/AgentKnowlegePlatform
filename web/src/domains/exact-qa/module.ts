/** 精准 QA 域描述符 —— 本域对外暴露的全部信息(路由 / 导航 / 识别色 / 审核渲染器)。 */

import { MessageSquareText } from 'lucide-react'

import type { DomainModule } from '../types'
import { qaPairActions } from './actions'
import { IngestPage } from './IngestPage'
import { QaItemCard, QaItemEditor, QaOriginPanel } from './renderers'

export const exactQaDomain: DomainModule = {
  key: 'exact_qa',
  label: 'Exact Q&A',
  path: '/ingest/exact-qa',
  icon: MessageSquareText,
  toneClass: 'bg-kb-exact-qa',
  IngestPage,
  renderers: {
    // item_type 取值见 server/app/models/ingest.py 的 ITEM_TYPES
    qa_pair: {
      label: 'Exact Q&A pair',
      card: QaItemCard,
      editor: QaItemEditor,
      origin: QaOriginPanel,
      // 采纳即发布 —— 审核台的动作层换成本域的两个端点(见 actions.ts)
      actions: qaPairActions,
    },
  },
}
