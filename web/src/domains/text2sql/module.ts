/** 智能问数(Text-to-SQL)域描述符。暂无审核渲染器(table_meta/metric/term 走 JSON 兜底)。 */

import { Database } from 'lucide-react'

import type { DomainModule } from '../types'
import { IngestPage } from './IngestPage'

export const text2sqlDomain: DomainModule = {
  key: 'text2sql',
  label: 'Text-to-SQL',
  path: '/ingest/text2sql',
  icon: Database,
  toneClass: 'bg-kb-text2sql',
  IngestPage,
}
