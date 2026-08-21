/** 精准 QA 域描述符。渲染器暂由 shared 层的 QaRenderers 提供(Stage 2 删除后走 JSON 兜底,
 *  真实渲染器由本域开发者在本文件夹内重写)。 */

import { MessageSquareText } from 'lucide-react'

import { QaItemCard, QaItemEditor, QaOriginPanel } from '@/components/staging/QaRenderers'

import type { DomainModule } from '../types'
import { IngestPage } from './IngestPage'

export const exactQaDomain: DomainModule = {
  key: 'exact_qa',
  label: 'Exact Q&A',
  path: '/ingest/exact-qa',
  icon: MessageSquareText,
  toneClass: 'bg-kb-exact-qa',
  IngestPage,
  renderers: {
    qa_pair: {
      label: 'QA pair',
      card: QaItemCard,
      editor: QaItemEditor,
      origin: QaOriginPanel,
    },
  },
}
