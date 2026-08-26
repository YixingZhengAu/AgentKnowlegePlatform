/** 调试台顶部那一条:一次检索里**真实发生过**的每一步。
 *
 * 四格就是流水线本身,从左读到右:两条腿各召回多少 → RRF 融合后剩多少 →
 * 重排到底跑没跑。数字下面各配一句人话,不是给作者看的,是给
 * "第一次听说这套检索"的人看的。
 *
 * 🩸 **第四格不是数字**:进重排的候选数就是 `recall.fused`(融合出来的全都送进去),
 * 再摆一个一模一样的数只会让人以为它们是两件事。所以那一格答的是"重排跑了吗" ——
 * 召回为空时它根本不会跑。
 *
 * 🩸 **`guard_fallback` 是这一页最值钱的一行**:cross-encoder 偶尔会整题失灵
 * (给所有候选都打了低于阈值的分),这时系统**丢掉它的排序,退回 RRF 名次**
 * (出处 `app/providers/cross_encoder_rerank.py` 的 guard 策略)。
 * 那一刻下面那份名单的顺序就不是重排序而是召回序,分数只剩参考价值 ——
 * 这句话必须摆在结果上面,不能当脚注。
 */

import { ShieldAlert } from 'lucide-react'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import type { SearchResult } from './schema'

/** 一格统计:大写标签 / 一个值 / 一句人话。值不一定是数字(重排那格是 Yes/No)。 */
type Stat = { label: string; value: string; hint: string }

/** 画一次检索的召回概况(四格 + guard 触发时的警示条)。
 *
 * @param result `GET /api/document/search` 的整份响应。
 */
export function RecallStrip({ result }: { result: SearchResult }) {
  const stats: Stat[] = [
    {
      label: 'Vector leg',
      value: String(result.recall.vector),
      hint: 'Chunks found by embedding similarity.',
    },
    {
      label: 'Keyword leg',
      value: String(result.recall.fts),
      hint: 'Chunks found by full-text search, stop-words stripped.',
    },
    {
      label: 'After RRF',
      value: String(result.recall.fused),
      hint: 'Both legs merged into one ranking by position.',
    },
    {
      label: 'Reranked',
      value: result.reranked ? 'Yes' : 'No',
      hint: result.reranked
        ? 'The cross-encoder re-scored every fused candidate.'
        : 'Skipped — there was nothing recalled to score.',
    },
  ]

  return (
    <Card className="overflow-hidden">
      <div className="flex items-stretch overflow-x-auto">
        {stats.map((stat, i) => (
          <div
            key={stat.label}
            className={cn(
              'min-w-[168px] flex-1 px-[26px] py-[18px]',
              i > 0 && 'border-l border-[var(--border-soft)]',
            )}
          >
            <div className="text-muted-foreground text-[11px] font-semibold tracking-[0.06em] uppercase">
              {stat.label}
            </div>
            <div className="font-display mt-1.5 text-[22px] font-bold tracking-[-0.02em]">
              {stat.value}
            </div>
            <p className="text-faint mt-1 text-[11.5px] leading-[1.5]">{stat.hint}</p>
          </div>
        ))}
      </div>

      {result.guard_fallback && (
        <div className="bg-warning-soft flex items-start gap-3 border-t border-[var(--border-soft)] px-[26px] py-4">
          <ShieldAlert className="text-warning mt-px size-[18px] shrink-0" />
          <div className="min-w-0">
            <div className="text-warning text-[13px] font-semibold">
              Rerank guard fired — this list is in RRF order
            </div>
            <p className="text-faint mt-1 max-w-[720px] text-[12px] leading-[1.6]">
              The cross-encoder scored every candidate below its confidence threshold, so its
              ordering was not trustworthy and was discarded; the results below are kept in the RRF
              recall order instead. The scores in that list are informational only.
            </p>
          </div>
        </div>
      )}
    </Card>
  )
}
