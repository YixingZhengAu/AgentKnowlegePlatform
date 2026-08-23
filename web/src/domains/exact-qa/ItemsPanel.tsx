/** 已发布的精准问答库 —— 采纳的终点在这里看得见。
 *
 * 两个字段是这一页的重点,别的都是陪衬:
 * - **Index faces**:这条 QA 有几行向量(标准问 + 每条相似问各一行)。它 >0 才意味着
 *   "现在真的能被检索命中";下线一条之后它会变成 0,而正式行仍然留着
 *   (历史消息里的引用不能悬空)。
 * - **Status**:active / disabled —— 下线不是删除。
 *
 * 列表不带答案正文(后端 `ExactQaItemOut` 刻意不给),点开某一行才查详情。
 */

import { BookCheck, ChevronDown, Power } from 'lucide-react'
import { useState } from 'react'

import { apiPost } from '@/api/client'
import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
import { StatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { fmtDateTime } from '@/lib/format'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

import type { QaItemDetail, QaItemList } from './schema'

export function ItemsPanel() {
  const [openId, setOpenId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const list = useApi<QaItemList>('/api/exact-qa/items')
  const detail = useApi<QaItemDetail>(openId ? `/api/exact-qa/items/${openId}` : null)

  const disable = async (id: string) => {
    setBusy(true)
    try {
      await apiPost(`/api/exact-qa/items/${id}/disable`)
      pushToast('success', 'Item disabled', 'Its vector rows were removed; the record is kept.')
      list.reload()
      if (openId === id) detail.reload()
    } catch {
      pushToast('error', 'disable_failed', 'Could not disable this item.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
        <BookCheck className="text-faint size-4" />
        <span className="text-[13px] font-semibold">Published Q&amp;A</span>
        <span className="text-faint ml-auto font-mono text-[11px]">
          {list.data?.items.length ?? 0} items
        </span>
      </div>

      <DataState
        state={list}
        isEmpty={(d) => d.items.length === 0}
        emptyIcon={BookCheck}
        emptyTitle="Nothing published yet"
        emptyDescription="Accepted candidates land here and become searchable immediately."
      >
        {(data) => (
          <ul className="flex flex-col gap-1.5 p-2">
            {data.items.map((item) => {
              const open = openId === item.id
              return (
                <li key={item.id}>
                  <div
                    className={cn(
                      'flex cursor-pointer items-center gap-3 rounded-[var(--radius-row)] border px-3.5 py-2.5 transition-all duration-150',
                      open
                        ? 'bg-selected border-[var(--selected-border)] shadow-[var(--shadow-row)]'
                        : 'hover:bg-subtle border-transparent',
                    )}
                    onClick={() => setOpenId(open ? null : item.id)}
                  >
                    <ChevronDown
                      className={cn(
                        'text-fainter size-4 shrink-0 transition-transform duration-150',
                        !open && '-rotate-90',
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <div
                        className={cn(
                          'mb-px truncate text-[13.5px] leading-[1.4]',
                          open ? 'text-primary font-semibold' : 'font-medium',
                        )}
                      >
                        {item.standard_question}
                      </div>
                      <div className="text-ghost font-mono text-[10.5px]">
                        {fmtDateTime(item.created_at)}
                      </div>
                    </div>
                    <Badge
                      tone={item.index_faces > 0 ? 'navy' : 'neutral'}
                      className="shrink-0 px-[9px] font-mono text-[11px] font-medium"
                    >
                      {item.index_faces} faces
                    </Badge>
                    <StatusBadge status={item.status} />
                  </div>

                  {open && (
                    <div className="bg-subtle mt-1.5 rounded-[var(--radius-panel)] px-[18px] py-[18px]">
                      {detail.data?.id === item.id ? (
                        <div className="flex flex-col gap-[18px]">
                          <Row label="Answer">
                            <p className="max-w-[680px] text-[13.5px] leading-[1.7] whitespace-pre-wrap">
                              {detail.data.answer}
                            </p>
                          </Row>
                          <Row label={`Similar questions (${detail.data.similar_count})`}>
                            <ul className="text-secondary-foreground flex flex-col gap-1 text-[12.5px]">
                              {detail.data.similar_questions.map((q) => (
                                <li key={q}>· {q}</li>
                              ))}
                            </ul>
                          </Row>
                          {detail.data.origin_ref && (
                            <Row label={`Source · page ${detail.data.origin_ref.page_idx + 1}`}>
                              <blockquote className="border-l-accent text-faint max-w-[680px] border-l-[3px] pl-3.5 text-[12.5px] leading-[1.7]">
                                {detail.data.origin_ref.quote}
                              </blockquote>
                            </Row>
                          )}
                          {/* 枚举是 enabled/disabled(出处 server/app/models/exact_qa.py QA_STATUSES),
                              不是 active —— 浏览器自测就是在这里抓到写错的 */}
                          {item.status === 'enabled' && (
                            <div>
                              <Button
                                variant="danger"
                                size="sm"
                                disabled={busy}
                                onClick={() => void disable(item.id)}
                              >
                                <Power /> Disable
                              </Button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-fainter font-mono text-[11px]">
                          loading…
                        </span>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </DataState>
    </Card>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[12.5px] font-semibold">{label}</span>
      {children}
    </div>
  )
}
