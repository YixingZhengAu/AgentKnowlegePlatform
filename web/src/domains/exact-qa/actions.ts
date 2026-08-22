/** qa_pair 的审核动作 —— 本域与 S0 泛型审核台唯一不同的那一层。
 *
 * **采纳即发布**(S1-plan §4 决策):没有"先标 approved、最后批量发布"这一步,
 * 点一下就是一个事务写 `exact_qa_items` + 建向量,下一秒就能被检索命中。
 * 所以这里换掉的正是动作:approve → `POST /candidates/{id}/accept`,
 * 而 payload 的编辑仍然走通用的 `PATCH /api/staging/{id}`(浅合并)。
 *
 * 三个刻意的取值:
 * - `requireRejectNote`:不采纳的理由是下一轮调 prompt 的素材,不能空着过(后端也会 422)
 * - `defaultStatusFilter: 'pending'`:审核台在本域是工作队列 —— 裁决完就该从视野消失
 * - `bulk: true` + `bulkApprove`:批量采纳一条条打本域接口(每条要建向量,没有批量端点);
 *   `bulkReject: false` —— 不采纳的理由必填,批量填一个理由等于没理由
 */

import { apiPatch, apiPost } from '@/api/client'
import type { StagingItem } from '@/api/schema'
import type { ReviewActions } from '@/components/staging/types'

export const qaPairActions: ReviewActions = {
  approveLabel: 'Accept & publish',
  requireRejectNote: true,
  defaultStatusFilter: 'pending',
  publish: false,
  bulk: true,
  bulkReject: false,

  approve: async (item, payload) => {
    // 先把未保存的改动落到 staging,再采纳 —— 顺序反了就会把改动前的内容发布出去
    if (payload) await apiPatch<StagingItem>(`/api/staging/${item.id}`, { payload })
    await apiPost<StagingItem>(`/api/exact-qa/candidates/${item.id}/accept`)
  },

  /** 批量采纳:**串行**,不并发。每条都要调一次 embedding 再写库,并发只是把
   *  限流风险和"一半成功一半失败"的概率一起放大;逐条来,失败的跳过并如实报数。 */
  bulkApprove: async (items) => {
    let ok = 0
    for (const item of items) {
      try {
        await apiPost<StagingItem>(`/api/exact-qa/candidates/${item.id}/accept`)
        ok += 1
      } catch {
        // 单条失败不该中断剩下的:审核台会按 ok/total 报出来
      }
    }
    return ok
  },

  reject: async (item, note) => {
    await apiPost<StagingItem>(`/api/exact-qa/candidates/${item.id}/reject`, { note })
  },
}
