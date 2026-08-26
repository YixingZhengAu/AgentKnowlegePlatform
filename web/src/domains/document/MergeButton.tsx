/** 「Merge with next」—— 审核台里就地补救切分的那一下(本域唯一的自定义动作)。
 *
 * 切分是自动的,偶尔把一句话的上下文拆两半。后端 `merge-next` 把下一条并进本条:
 * 本条变 `modified`,被并的那条变 `rejected`(不再发布),**seq 不重排**。
 *
 * 🩸 **合并之后为什么要整页刷新**:它一次改两条候选(本条内容变长、下一条被驳回),
 * 而审核台没有把"重查列表"暴露给渲染器(渲染器契约里没有任何刷新钩子)。
 * 不刷新的话编辑区还捧着合并前的文本,此时点「Save changes」会把合并结果**覆盖回去** ——
 * 那是丢数据,比刷新一下难受得多。所以留一拍让 toast 被看见,然后重载。
 */

import { Loader2, Merge } from 'lucide-react'
import { useState } from 'react'

import { ApiError, apiPost } from '@/api/client'
import { Button } from '@/components/ui/button'
import { pushToast } from '@/lib/toast'

import type { MergeResult } from './schema'

/** 合并成功后到重载之间的停顿:够读完那条 toast,不至于像页面自己崩了 */
const RELOAD_DELAY_MS = 1200

/** 合并失败时给人话 —— 后端的 code 是契约,message 是给开发看的。 */
const FAILURE_TEXT: Record<string, string> = {
  no_next_chunk: 'This is the last chunk of the document — there is nothing after it to merge.',
  job_not_reviewable: 'This job is no longer open for review, so chunks can no longer be merged.',
}

/** 把当前切片与紧随其后的那条合并成一条。
 *
 * @param itemId 当前候选的 staging item id(由 origin 槽的 `item` 直接给出)。
 */
export function MergeButton({ itemId }: { itemId: string }) {
  const [busy, setBusy] = useState(false)

  const merge = async () => {
    setBusy(true)
    try {
      const res = await apiPost<MergeResult>(`/api/document/candidates/${itemId}/merge-next`)
      pushToast(
        'success',
        'Chunks merged',
        `The next chunk was folded into this one (${res.token_count} tokens). Reloading the review console…`,
      )
      window.setTimeout(() => window.location.reload(), RELOAD_DELAY_MS)
    } catch (error) {
      const code = error instanceof ApiError ? error.code : 'merge_failed'
      pushToast(
        'error',
        code,
        FAILURE_TEXT[code] ?? 'Could not merge this chunk with the next one.',
      )
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <Button
        type="button"
        size="sm"
        variant="secondary"
        disabled={busy}
        onClick={() => void merge()}
      >
        {busy ? <Loader2 className="animate-spin" /> : <Merge />}
        Merge with next
      </Button>
      <span className="text-ghost text-[11.5px] leading-[1.5]">
        Use this when the splitter cut one thought in half. The next chunk is folded into this one
        and is no longer published on its own.
      </span>
    </div>
  )
}
