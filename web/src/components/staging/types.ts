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

/** 审核台的**动作层**(S1-plan Step 7a 加出来的一层)。
 *
 * 为什么要把动作抽出来:审核台的流程(筛选/排序/键盘流/选中推导)对三类知识是同一套,
 * 但"通过"这个动作各域可以完全不同 —— S0 泛型语义是"标为 approved,最后批量发布",
 * S1 是**采纳即发布**(一个事务写正式表 + 建向量,没有批量发布这一步)。
 * 不抽这一层就只有两条烂路:要么在泛型组件里 if 域名,要么各域复制一份审核台。
 *
 * 不传就用 S0 的默认实现(`PATCH /api/staging/{id}` + `POST /api/jobs/{id}/publish`)。
 */
export type ReviewActions = {
  /** 主动作按钮文案(S0 "Approve" / S1 "Accept & publish") */
  approveLabel: string
  /** 驳回必须填理由(S1:不采纳的理由是下一轮调 prompt 的素材,不能空着过) */
  requireRejectNote?: boolean
  /** 列表默认筛选。S1 的审核台是工作队列 —— 裁决完的就该从视野里消失,默认只看 pending */
  defaultStatusFilter?: string
  /** 有没有"批量发布"这一步(S1 采纳即发布 → false,按钮不出现) */
  publish?: boolean
  /** 有没有批量勾选(false 时勾选框与空格键一并消失,不留死按钮) */
  bulk?: boolean
  /** 批量通过的实现。不给就走 S0 的 `/api/staging/bulk`(只改 review_status);
   *  S1 的"采纳"要写正式表 + 建向量,只能逐条打本域接口,所以必须由本域给实现。
   *  返回真正成功的条数 —— 中途失败要能如实报"5 条里成了 3 条",不许假装全成了 */
  bulkApprove?: (items: StagingItem[]) => Promise<number>
  /** 允不允许批量驳回(默认允许)。S1 关掉:不采纳的理由必填,逐条填才有意义 */
  bulkReject?: boolean
  /** 通过。`payload` 非 null = 带着未保存的改动一起提交。
   *  返回值一律被丢弃(审核台自己重查列表),所以写 `Promise<unknown>` 而不是 void ——
   *  否则每个实现都得在末尾补一句 `void` 只为迎合类型 */
  approve: (item: StagingItem, payload: Payload | null) => Promise<unknown>
  reject: (item: StagingItem, note: string) => Promise<unknown>
}

/** 一类知识的渲染器三件套(originPanel 可选:文档 RAG 才需要原文对照)。 */
export type ItemRenderers = {
  label: string
  card: ComponentType<ItemCardProps>
  editor: ComponentType<ItemEditorProps>
  origin?: ComponentType<OriginPanelProps>
  /** 原文面板放哪(**布局提示,由域声明,壳不猜**):
   *  - `'below'`(默认)= 画在编辑区正下方,S1/S3 维持原样;
   *  - `'side'` = 左原文右编辑并排,可收起 —— 审切片的问题是"这一刀切得对不对",
   *    原文和结果必须同屏(S2-PLAN 附录三 F2)。
   *  没有 origin 渲染器时本字段无意义。 */
  originPlacement?: 'below' | 'side'
  /** 本类知识的审核动作;不给就走 S0 泛型默认(approve/reject + 批量发布) */
  actions?: ReviewActions
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
