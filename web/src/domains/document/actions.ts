/** `chunk` 的审核动作 —— 本域**保留 S0 的泛型语义**,只换两处措辞与纪律。
 *
 * ★ **采纳 ≠ 发布**:切片是"标 approved → 最后一次性发布整批"(`publish: true`),
 * 与 S1 的"采纳即发布"相反。原因是切片要整份文档一起进索引才有意义 ——
 * 半份文档的向量库,检索出来的答案会缺上下文。
 *
 * 两处覆盖:
 * 1. `approveLabel: 'Keep chunk'` —— 审的不是"这条对不对",是"这条要不要留在索引里";
 *    切分产物大多合格,按钮文案要说得像日常操作,不像判决。
 * 2. `requireRejectNote: false` —— 丢一条切片的理由通常就是"这页是目录/版权页",
 *    强迫写理由只会让人乱敲一个字符;S1 那条纪律(理由是调 prompt 的素材)在这里不成立。
 *
 * `approve` / `reject` 刻意与 `StagingReview` 的 `DEFAULT_ACTIONS` 同实现(通用
 * `PATCH /api/staging/{id}`)—— 本域没有自己的采纳端点,只有一个 `merge-next`,
 * 它不属于"通过/驳回"这条轴,所以挂在编辑器里(见 `MergeButton.tsx`)。
 * 默认实现没有导出,只能照抄一份;这份要跟着 DEFAULT_ACTIONS 一起改。
 */

import { apiPatch } from '@/api/client'
import type { StagingItem } from '@/api/schema'
import type { ReviewActions } from '@/components/staging/types'

export const chunkActions: ReviewActions = {
  approveLabel: 'Keep chunk',
  requireRejectNote: false,
  publish: true,
  bulk: true,

  approve: (item, payload) =>
    apiPatch<StagingItem>(`/api/staging/${item.id}`, { review_status: 'approved', payload }),

  reject: (item: StagingItem, note: string) =>
    apiPatch<StagingItem>(`/api/staging/${item.id}`, {
      review_status: 'rejected',
      review_note: note || null,
      payload: null,
    }),
}
