/** 智能问数(Text-to-SQL)域描述符 —— 本域对外暴露的全部信息
 *  (路由 / 导航 / 识别色 / `sql_intent` 审核渲染器 / `sql` 引用渲染器)。 */

import { Database } from 'lucide-react'

import type { DomainModule } from '../types'
import { sqlIntentActions } from './actions'
import { IngestPage } from './IngestPage'
import { IntentItemCard, IntentItemEditor } from './renderers'
import { SqlCitationCard } from './SqlCitation'

export const text2sqlDomain: DomainModule = {
  key: 'text2sql',
  label: 'Text-to-SQL',
  path: '/ingest/text2sql',
  icon: Database,
  toneClass: 'bg-kb-text2sql',
  IngestPage,
  renderers: {
    // item_type 取值见 server/app/models/ingest.py 的 ITEM_TYPES
    sql_intent: {
      label: 'Question intent',
      card: IntentItemCard,
      editor: IntentItemEditor,
      // 采纳 ≠ 发布:采纳只建 draft 意图,验收在意图详情页(见 actions.ts)
      actions: sqlIntentActions,
    },
  },
  citations: {
    // citation_type 取值见 server/app/services/text2sql/runtime.py::citations
    sql: SqlCitationCard,
  },
}
