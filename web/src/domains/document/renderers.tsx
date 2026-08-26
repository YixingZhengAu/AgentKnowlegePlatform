/** chunk 的审核渲染器三件套 —— 泛型审核台(`components/StagingReview`)的本域实例。
 *
 * 契约见 `components/staging/types.ts`。审核台负责流程,这三个组件只回答三个问题:
 *   1. 这条切片在一行里怎么一眼看懂(`ChunkItemCard`)
 *   2. 怎么改(`ChunkItemEditor`)—— 只有正文一个输入框,因为**只有正文会被检索**
 *   3. 它出自原文哪里(`ChunkOriginPanel`)—— PDF 翻到那一页 + 图表对照 + 合并动作
 *
 * 🩸 **为什么合并按钮和图表在 origin 槽而不在 editor 槽**:
 * `ItemEditorProps` 只有 `{payload, onChange, disabled}`,**拿不到 `StagingItem`** ——
 * 而合并要 `item.id`、图片地址要 `origin_ref.document_id`,两者 payload 里都没有。
 * `OriginPanelProps` 有完整的 `item`,而且它就渲染在编辑区正下方,同一个右栏里。
 * 与其绕一个"卡片渲染时把 id 记进模块级 Map、编辑器再按 seq 查回来"的机关
 * (渲染期副作用,列表一虚拟化就会失效),不如用这个本来就拿得到身份的槽。
 */

import type { ItemCardProps, ItemEditorProps, OriginPanelProps } from '@/components/staging/types'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'

import { FigureList } from './FigureList'
import { documentPdfUrl } from './files'
import { MergeButton } from './MergeButton'
import { readChunkPayload, readOriginRef, shortHeadingPath } from './schema'

/** 列表里的一行:序号 / 标题路径 / token 数 / 图表种类 / 正文首句。 */
export function ChunkItemCard({ item }: ItemCardProps) {
  const chunk = readChunkPayload(item.payload)
  const kinds = [...new Set(chunk.figures.map((f) => f.kind))]
  const heading = shortHeadingPath(chunk.heading_path)

  return (
    <div className="min-w-0">
      <div className="mb-px flex items-center gap-2">
        <span className="text-fainter font-mono text-[10.5px]">#{chunk.seq}</span>
        {/* 标题路径按层级截断,不按字符 —— 从单词中间切开会看着像解析坏了 */}
        <span className="truncate text-[13.5px] leading-[1.4] font-medium [.is-sel_&]:font-semibold [.is-sel_&]:text-[var(--primary)]">
          {heading || 'Untitled section'}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-fainter shrink-0 font-mono text-[10.5px]">
          {chunk.token_count} tok
        </span>
        {kinds.map((kind) => (
          <Badge key={kind} tone="navy" className="h-[18px] px-2 text-[10px]">
            {kind}
          </Badge>
        ))}
        <span className="text-ghost truncate text-[11.5px] leading-[1.4]">{chunk.content}</span>
      </div>
    </div>
  )
}

/** 编辑区:一个正文输入框。改这里等于改知识本身 —— 被嵌入、被检索的就是这段文本。 */
export function ChunkItemEditor({ payload, onChange, disabled }: ItemEditorProps) {
  const chunk = readChunkPayload(payload)
  const heading = chunk.heading_path.join(' > ')

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">chunk #{chunk.seq}</Badge>
        <span className="text-faint font-mono text-[11px]">{chunk.token_count} tokens</span>
        <span className="text-faint font-mono text-[11px]">page {chunk.page_idx + 1}</span>
      </div>

      {heading && <div className="text-faint text-[12px] leading-[1.5] break-words">{heading}</div>}

      <label className="flex flex-col gap-2">
        <span className="text-[12.5px] font-semibold">Chunk text</span>
        <Textarea
          rows={16}
          className="text-[13.5px] leading-[1.75]"
          value={chunk.content}
          disabled={disabled}
          onChange={(e) => onChange({ content: e.target.value })}
        />
        <span className="text-ghost text-[11.5px] leading-[1.5]">
          This exact text is embedded and retrieved. Figures appear as a description line followed
          by an image link — keep both lines together.
        </span>
      </label>
    </div>
  )
}

/** 原文对照 + 图表 + 合并动作 —— 右栏里紧接编辑区的那一块。 */
export function ChunkOriginPanel({ item }: OriginPanelProps) {
  const origin = readOriginRef(item.origin_ref)
  if (!origin) {
    return <p className="text-ghost text-[12.5px]">No source reference on this item.</p>
  }
  const chunk = readChunkPayload(item.payload)
  const page = origin.page + 1
  const heading = shortHeadingPath(chunk.heading_path, 3)

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="navy">page {page}</Badge>
          {heading && <span className="text-faint truncate text-[12px]">{heading}</span>}
        </div>
        {/* 浏览器原生 PDF 阅读器:需要的只是"翻到第 N 页对着看",不值得引 pdf.js */}
        <iframe
          key={`${origin.document_id}#${page}`}
          src={documentPdfUrl(origin.document_id, page)}
          title={`Source PDF, page ${page}`}
          className="h-[460px] w-full rounded-[var(--radius)] border border-[var(--border)]"
        />
      </div>

      <FigureList figures={chunk.figures} documentId={origin.document_id} />

      <div className="border-t border-[var(--border-soft)] pt-4">
        <MergeButton itemId={item.id} />
      </div>
    </div>
  )
}
