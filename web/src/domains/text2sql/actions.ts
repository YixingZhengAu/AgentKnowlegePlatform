/** `sql_intent` 的审核动作 —— 与 S1 最大的不同就在这一层。
 *
 * ★ **采纳 ≠ 发布**(出处 `services/text2sql/publisher.py` 头部):
 *
 * ```
 * 候选意图 ──采纳──▶ sql_intents(draft)── 详情页迭代 ──▶ 发布(建索引面)
 *   审核台            还没有 SQL、没有参数区      生成模板 → Run → 参数区 → 问法
 * ```
 *
 * S1 是"采纳即发布"(点一下就进检索),因为它审的是一段文本对不对;S3 审的是
 * **这条问题值不值得做成模板** —— "这条 SQL 出的数对不对"要在详情页看真数据才能判。
 * 所以本域**保留 S0 的泛型语义**(标 approved → 批量发布),只换三处措辞与纪律:
 *
 * 1. `approveLabel: 'Adopt as draft'` —— 让"这一下不会让它上线"写在按钮上;
 * 2. `requireRejectNote` —— 不采纳的理由是下一轮调 prompt 的素材(与 S1 同一条纪律);
 * 3. `bulkReject: false` —— 理由必填,批量填同一个理由等于没理由。
 *
 * ⚠ 审核台那颗批量按钮的文案是共享组件里写死的 `Publish N approved`;在本域它做的事是
 * "把这些候选采纳成 draft 意图"。改它属于 shared 层措辞变更,留给集成者(记在 S3-PLAN)。
 */

import { apiPatch } from '@/api/client'
import type { StagingItem } from '@/api/schema'
import type { ReviewActions } from '@/components/staging/types'

export const sqlIntentActions: ReviewActions = {
  approveLabel: 'Adopt as draft',
  requireRejectNote: true,
  defaultStatusFilter: 'pending',
  publish: true,
  bulk: true,
  bulkReject: false,

  // 采纳走通用接口:真正写 sql_intents 的是后端注册的 publisher,批量发布那一步才调它
  approve: (item, payload) =>
    apiPatch<StagingItem>(`/api/staging/${item.id}`, { review_status: 'approved', payload }),

  reject: (item, note) =>
    apiPatch<StagingItem>(`/api/staging/${item.id}`, {
      review_status: 'rejected',
      review_note: note,
      payload: null,
    }),
}
