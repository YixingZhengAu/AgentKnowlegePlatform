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
      <div className="flex items-center gap-2 border-b px-5 py-3">
        <BookCheck className="text-muted-foreground size-4" />
        <span className="font-display text-[16px] font-semibold">Published Q&amp;A</span>
        <span className="text-muted-foreground ml-auto font-mono text-[11px]">
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
          <ul>
            {data.items.map((item) => {
              const open = openId === item.id
              return (
                <li key={item.id} className="border-b last:border-0">
                  <div
                    className={cn(
                      'hover:bg-subtle flex cursor-pointer items-center gap-3 px-5 py-3',
                      open && 'bg-primary-soft',
                    )}
                    onClick={() => setOpenId(open ? null : item.id)}
                  >
                    <ChevronDown
                      className={cn(
                        'text-muted-foreground size-4 shrink-0 transition-transform',
                        !open && '-rotate-90',
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] font-medium">
                        {item.standard_question}
                      </div>
                      <div className="text-muted-foreground font-mono text-[11px]">
                        {fmtDateTime(item.created_at)}
                      </div>
                    </div>
                    <Badge tone={item.index_faces > 0 ? 'navy' : 'neutral'} className="font-mono">
                      {item.index_faces} faces
                    </Badge>
                    <StatusBadge status={item.status} />
                  </div>

                  {open && (
                    <div className="bg-subtle border-t px-5 py-4">
                      {detail.data?.id === item.id ? (
                        <div className="flex flex-col gap-3">
                          <Row label="Answer">
                            <p className="text-[13px] leading-relaxed whitespace-pre-wrap">
                              {detail.data.answer}
                            </p>
                          </Row>
                          <Row label={`Similar questions (${detail.data.similar_count})`}>
                            <ul className="text-muted-foreground flex flex-col gap-0.5 text-[12px]">
                              {detail.data.similar_questions.map((q) => (
                                <li key={q}>· {q}</li>
                              ))}
                            </ul>
                          </Row>
                          {detail.data.origin_ref && (
                            <Row label={`Source · page ${detail.data.origin_ref.page_idx + 1}`}>
                              <blockquote className="border-l-primary border-l-[3px] pl-3 text-[12px] leading-relaxed">
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
                        <span className="text-muted-foreground font-mono text-[11px]">
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
    <div className="flex flex-col gap-1">
      <span className="text-muted-foreground font-mono text-[11px] tracking-wide uppercase">
        {label}
      </span>
      {children}
    </div>
  )
}
