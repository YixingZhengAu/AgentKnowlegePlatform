/** 切片管理页 —— 一份文档**发布之后**的样子:索引里现在到底躺着哪些切片。
 *
 * 🩸 它和审核台(`/jobs/:jobId/review`)是两个不同的页面,动作也不是一回事:
 * 审核台处理的是 `staging_items` 里的候选,"不采纳"发生在发布之前、不可逆;
 * 这一页处理的是 `chunks` 里的正式行,"禁用"发生在发布之后、可逆。
 *
 * 四个设计决定:
 *
 * 1. **号码的空洞要看得见**(细节见 `ChunkTable.tsx`):seq 发布时钉死,审核里被拿掉的
 *    那几条留下的洞,就是检索做上下文扩展(seq±1)时会跳号的原因。
 * 2. **向量状态与 status 分两列摆**:禁用会把 `embedding` 清空,两列一起看才知道
 *    "下线"到底做了什么;也才解释得了"启用要等一下"(那是在重算向量)。
 * 3. **改完就地更新那一行,不整页重载**。启用/禁用的回执 `ChunkStatusResult` 已经带回
 *    新的 `status` 与 `embedded`,再拉一遍整份列表只会让人眼前一闪。
 * 4. **退休行默认藏起来**。它们由后端的 `retired` 旗标标出(**不要自己判 `seq < 0`** —— 给到前端的 `seq` 已经
 *    还原成当初的编号了),只为历史会话的引用还解析得到而留着;
 *    混在"这份文档现在是什么样"里会让人以为索引里有两份。
 */

import { ArrowLeft, Layers } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useApi } from '@/api/hooks'
import { DataState } from '@/components/DataState'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Segmented, SegmentedItem } from '@/components/ui/segmented'

import { ChunkTable } from './ChunkTable'
import { ReingestCard } from './ReingestCard'
import {
  STAGE_LABEL,
  stageTone,
  type ChunkStatusResult,
  type DocumentOut,
  type PublishedChunk,
  type PublishedChunkList,
} from './schema'

export function ChunksPage() {
  const { documentId } = useParams<{ documentId: string }>()
  const docId = documentId ?? ''
  const [showRetired, setShowRetired] = useState(false)
  // 就地更新用的补丁:chunk id → 最新的 status/embedded。列表数据本身不动。
  const [patches, setPatches] = useState<Record<string, ChunkStatusResult>>({})

  const doc = useApi<DocumentOut>(docId ? `/api/document/documents/${docId}` : null)
  const chunks = useApi<PublishedChunkList>(
    docId
      ? `/api/document/documents/${docId}/chunks${showRetired ? '?include_retired=true' : ''}`
      : null,
  )

  const onChanged = (result: ChunkStatusResult) =>
    setPatches((prev) => ({ ...prev, [result.id]: result }))

  const items = (chunks.data?.items ?? []).map(patch(patches))
  const live = items.filter((c) => !c.retired)
  const tokens = live.reduce((sum, c) => sum + (c.token_count ?? 0), 0)

  return (
    <div className="flex flex-col gap-5">
      <div className="-mt-1 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <Link
          to="/ingest/document"
          className="text-secondary-foreground hover:text-primary flex items-center gap-1.5 text-[13px] transition-colors"
        >
          <ArrowLeft className="size-3.5" /> Documents
        </Link>
        <span className="bg-kb-document size-2.5 rounded-full" />
        <span className="text-[13px] font-semibold">{doc.data?.name ?? '…'}</span>
        {doc.data && (
          <Badge tone={stageTone(doc.data.stage)}>
            {STAGE_LABEL[doc.data.stage] ?? doc.data.stage}
          </Badge>
        )}
        <span className="text-faint font-mono text-[11px]">
          {live.length} chunks · {tokens.toLocaleString('en-AU')} tokens
        </span>
      </div>

      <ReingestCard
        documentId={docId}
        liveChunks={live.filter((c) => c.status === 'active').length}
        onSubmitted={() => {
          doc.reload()
          chunks.reload()
        }}
      />

      <Card className="overflow-hidden">
        <div className="flex h-[54px] items-center gap-2.5 border-b border-[var(--border-soft)] px-[26px]">
          <Layers className="text-faint size-4" />
          <span className="text-[13px] font-semibold">Published chunks</span>
          <Segmented className="ml-auto">
            <SegmentedItem
              active={!showRetired}
              label="Live"
              onClick={() => setShowRetired(false)}
            />
            <SegmentedItem
              active={showRetired}
              label="Include retired"
              onClick={() => setShowRetired(true)}
            />
          </Segmented>
        </div>
        <DataState
          state={chunks}
          isEmpty={(d) => d.items.length === 0}
          emptyIcon={Layers}
          emptyTitle="Nothing published yet"
          emptyDescription="Chunks land here once a review batch is published."
        >
          {() => <ChunkTable items={items} documentId={docId} onChanged={onChanged} />}
        </DataState>
      </Card>
    </div>
  )
}

/** 把补丁盖到一条切片上 —— 只有 `status` / `embedded` 会被动作改到。 */
function patch(patches: Record<string, ChunkStatusResult>) {
  return (chunk: PublishedChunk): PublishedChunk => {
    const p = patches[chunk.id]
    return p ? { ...chunk, status: p.status, embedded: p.embedded } : chunk
  }
}
