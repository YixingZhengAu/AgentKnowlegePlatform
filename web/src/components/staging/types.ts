/** 审核台的渲染器契约 —— 泛型组件与"某类知识长什么样"之间的唯一接口。
 *
 * S1/S2/S3 各写一对渲染器就能复用整个审核台:筛选、排序、批量、键盘流、发布
 * 全在 `<StagingReview>` 里,渲染器只回答两个问题:
 *   1. 这条东西在列表里怎么一眼看懂(`ItemCard`)
 *   2. 这条东西怎么改(`ItemEditor`)
 *
 * `payload` 是 jsonb(结构见 DB-DESIGN §8),所以这里的类型只能是宽松的记录 ——
 * 泛型审核台的全部意义就是**不认识** payload 里有什么。
 */

import type { ComponentType } from 'react'

import type { StagingItem } from '@/api/schema'

export type Payload = Record<string, unknown>

export type ItemCardProps = { item: StagingItem }

export type ItemEditorProps = {
  payload: Payload
  /** 只回传改动的顶层键(后端是浅合并),不必回传整个 payload */
  onChange: (patch: Payload) => void
  disabled?: boolean
}

export type OriginPanelProps = { item: StagingItem }

/** 一类知识的渲染器三件套(originPanel 可选:文档 RAG 才需要原文对照)。 */
export type ItemRenderers = {
  label: string
  card: ComponentType<ItemCardProps>
  editor: ComponentType<ItemEditorProps>
  origin?: ComponentType<OriginPanelProps>
}

/** payload 里取字符串/字符串数组的小工具:jsonb 来的东西不能假设类型。 */
export function str(payload: Payload, key: string): string {
  const v = payload[key]
  return typeof v === 'string' ? v : ''
}

export function strList(payload: Payload, key: string): string[] {
  const v = payload[key]
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
}
