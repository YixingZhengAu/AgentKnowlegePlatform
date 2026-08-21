/** 精准 QA 域描述符。审核渲染器尚未注册(qa_pair 走 JSON 兜底),
 *  真实渲染器由本域开发者在本文件夹内实现后在 renderers 登记。 */

import { MessageSquareText } from 'lucide-react'

import type { DomainModule } from '../types'
import { IngestPage } from './IngestPage'

export const exactQaDomain: DomainModule = {
  key: 'exact_qa',
  label: 'Exact Q&A',
  path: '/ingest/exact-qa',
  icon: MessageSquareText,
  toneClass: 'bg-kb-exact-qa',
  IngestPage,
}
