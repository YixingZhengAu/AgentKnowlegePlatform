/** 检索调试台 —— 问一句话,看混合检索**真的**做了什么。
 *
 * 这一页存在的理由是一个问题:"你们的 RAG 到底怎么检索?" 它要能不靠一张 PPT 就答完:
 * 两条腿各召回多少、RRF 融合后剩多少、重排跑没跑(以及 guard 有没有把它的排序丢掉)、
 * 每一条是被哪条腿找到的。
 *
 * 三个设计决定:
 *
 * 1. **问题存进 URL 的 `?q=`**,不存组件 state。于是一次结果可以直接把地址发给别人,
 *    刷新页面也还在原处 —— 演示时最怕"你再打一遍那个问题"。
 * 2. **取数完全由 `?q=` 驱动**:`useApi` 的 path 为 `null` 就不发请求,
 *    URL 一变 path 就变、请求自动重发,不用自己写一个 submit 分支去 fetch。
 * 3. **"没结果"分两种说法**:`recall.fused === 0` 是两条腿都没召回(库里没有这回事),
 *    `fused > 0` 而 hits 为空是召回了但一条都没留下 —— 后者是检索问题,前者是数据问题,
 *    混成一句 "No results" 就把最该看见的区别抹掉了。
 */

import { ListOrdered, Loader2, Search, SearchX } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { pushToast } from '@/lib/toast'

import { RecallStrip } from './RecallStrip'
import type { SearchResult } from './schema'
import { SearchHitRow } from './SearchHitRow'

export function SearchConsolePage() {
  const [params, setParams] = useSearchParams()
  const query = (params.get('q') ?? '').trim()

  const search = useApi<SearchResult>(
    query ? `/api/document/search?q=${encodeURIComponent(query)}` : null,
  )

  const submit = (next: string) => {
    if (!next) {
      pushToast('info', 'Type a question first', 'The retriever needs something to search for.')
      return
    }
    // 同一个问题再点一次是"重跑一遍"(比如刚发布了新切片),URL 不变就手动重取
    if (next === query) search.reload()
    else setParams({ q: next })
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="-mt-1 flex items-center gap-2.5">
        <span className="bg-kb-document size-2.5 rounded-full" />
        <span className="text-faint text-[13px]">Document RAG retrieval</span>
      </div>

      <Card className="flex flex-col gap-[18px] px-[26px] py-[22px]">
        <div className="flex items-start gap-[18px]">
          <span className="bg-subtle flex size-10 shrink-0 items-center justify-center rounded-[var(--radius)]">
            <Search className="text-faint size-[18px]" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="font-display mb-1 text-[14px] font-bold tracking-[-0.01em]">
              Ask the retriever
            </div>
            <p className="text-faint max-w-[640px] text-[12.5px] leading-[1.6]">
              A question runs down two legs at once — a vector search over the chunk embeddings, and
              a Postgres full-text search over the same chunks with stop-words stripped. Reciprocal
              Rank Fusion merges the two rankings by position rather than by score, because cosine
              similarity and <span className="font-mono text-[11.5px]">ts_rank</span> are not on the
              same scale. The fused candidates then go through a cross-encoder that re-scores each
              one against the question; a guard keeps the fusion order instead whenever that
              re-scoring pass looks unreliable.
            </p>
          </div>
        </div>

        {/* key = 当前问题:前进/后退换了 `?q=`,输入框靠换 key 重置,不用 effect 回写 */}
        <QueryBar key={query} initial={query} busy={search.loading} onSubmit={submit} />
        <p className="text-fainter text-[11.5px]">
          The rerank score is a raw cross-encoder logit, so it is often negative — only the ordering
          means anything, not the sign or the size.
        </p>
      </Card>

      {search.data && <RecallStrip result={search.data} />}

      <Card className="overflow-hidden">
        <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
          <ListOrdered className="text-faint size-4" />
          <span className="text-[13px] font-semibold">Ranked results</span>
          {search.data && (
            <span className="text-faint ml-auto font-mono text-[11px]">
              {search.data.hits.length} of {search.data.recall.fused} candidates
            </span>
          )}
        </div>
        <DataState
          state={search}
          emptyIcon={Search}
          emptyTitle="Nothing searched yet"
          emptyDescription="Type a question above to see both recall legs, the fused ranking and the rerank scores."
        >
          {(data) =>
            data.hits.length === 0 ? (
              <NoHits result={data} />
            ) : (
              <div>
                {data.hits.map((hit, i) => (
                  <SearchHitRow key={hit.chunk_id} hit={hit} position={i + 1} />
                ))}
              </div>
            )
          }
        </DataState>
      </Card>
    </div>
  )
}

/** 输入框 + Search 按钮。自己拿着草稿态,由外面换 key 来重置。
 *
 * 用 `<form>` 是为了白拿回车提交,不用自己听 keydown。
 */
function QueryBar({
  initial,
  busy,
  onSubmit,
}: {
  initial: string
  busy: boolean
  onSubmit: (query: string) => void
}) {
  const [draft, setDraft] = useState(initial)
  return (
    <form
      className="flex flex-wrap items-center gap-2.5"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit(draft.trim())
      }}
    >
      <Input
        value={draft}
        placeholder="How long is the warranty on the HC-430 inverter?"
        aria-label="Question"
        className="min-w-[280px] flex-1"
        onChange={(e) => setDraft(e.target.value)}
      />
      <Button type="submit" variant="accent" size="sm" disabled={busy}>
        {busy ? <Loader2 className="animate-spin" /> : <Search />}
        {busy ? 'Searching…' : 'Search'}
      </Button>
    </form>
  )
}

/** 两种"没结果"是两件不同的事,措辞必须分开 —— 一个是数据问题,一个是检索问题。 */
function NoHits({ result }: { result: SearchResult }) {
  if (result.recall.fused === 0) {
    return (
      <EmptyState
        icon={SearchX}
        title="Nothing was recalled"
        description="Neither the vector leg nor the keyword leg found a single chunk for this question. Either the knowledge base holds nothing on this topic, or the document has not been published yet."
      />
    )
  }
  return (
    <EmptyState
      icon={SearchX}
      title="Recalled, then filtered out"
      description={`Both legs together recalled ${result.recall.fused} candidates, but none of them survived the rerank step. The chunks exist — this is a ranking problem, not a missing-content problem.`}
    />
  )
}
