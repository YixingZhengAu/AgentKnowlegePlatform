/** item_type -> 渲染器 的注册表。
 *
 * 渲染器由各域在自己的 `domains/<域>/module.ts` 描述符里登记,这里只做汇总 ——
 * 本文件不认识任何具体域。没登记的类型走 JSON 兜底,界面不会空着。
 */

import { DOMAINS } from '@/domains'

import { JsonItemCard, JsonItemEditor } from './JsonRenderers'
import type { ItemRenderers } from './types'

export const FALLBACK_RENDERERS: ItemRenderers = {
  label: 'Raw item',
  card: JsonItemCard,
  editor: JsonItemEditor,
}

// key 取值见 server/app/models/ingest.py 的 ITEM_TYPES
export const RENDERERS: Record<string, ItemRenderers> = Object.assign(
  {},
  ...DOMAINS.map((d) => d.renderers ?? {}),
)

export function renderersFor(itemType: string | undefined): ItemRenderers {
  return (itemType && RENDERERS[itemType]) || FALLBACK_RENDERERS
}
