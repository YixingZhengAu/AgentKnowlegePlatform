/** item_type -> 渲染器 的注册表。
 *
 * 加一类知识 = 在这里加一行(S1 已经有 qa_pair;S2 的 chunk、S3 的 table_meta/metric/term
 * 各补一行),审核台本身不动。没登记的类型走 JSON 兜底,界面不会空着。
 */

import { JsonItemCard, JsonItemEditor } from './JsonRenderers'
import { QaItemCard, QaItemEditor, QaOriginPanel } from './QaRenderers'
import type { ItemRenderers } from './types'

export const FALLBACK_RENDERERS: ItemRenderers = {
  label: 'Raw item',
  card: JsonItemCard,
  editor: JsonItemEditor,
}

// key 取值见 server/app/models/ingest.py 的 ITEM_TYPES
export const RENDERERS: Record<string, ItemRenderers> = {
  qa_pair: {
    label: 'QA pair',
    card: QaItemCard,
    editor: QaItemEditor,
    origin: QaOriginPanel,
  },
}

export function renderersFor(itemType: string | undefined): ItemRenderers {
  return (itemType && RENDERERS[itemType]) || FALLBACK_RENDERERS
}
