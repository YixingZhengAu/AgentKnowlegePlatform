/** 切片管理页的一行:已发布的**正式行**(`chunks`),不是待审候选(`staging_items`)。
 *
 * 三个要在界面上看得见的事实:
 *
 * 1. **向量状态与 status 是两件事**。禁用会把 `embedding` 清空(留着就是 HNSW 索引里
 *    一条永远不该被命中的死数据),所以这一行同时摆 `status` 和 `embedded` ——
 *    看到"disabled + no vector"才算真的理解了下线做了什么。
 * 2. **启用不是瞬时操作**:向量被清了,重新上线要重算一次 embedding(一次 Embedding 调用),
 *    所以那颗按钮必须有 loading 态,不能装成状态位翻转。
 * 3. **退休行没有动作**。它由后端的 `retired` 旗标标出,只为历史会话的引用还读得到而留着;
 *    正文早被新一版取代,放回索引就会和新行重复(后端也会用 `chunk_retired` 挡掉)。
 */

import { ChevronDown, EyeOff, Images, Loader2, RotateCw } from 'lucide-react'
import { useState } from 'react'

import { ApiError, apiPost } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TD, TR } from '@/components/ui/table'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

import { ChunkContent } from './ChunkContent'
import { chunkFailureText, chunkPreview, CHUNK_COLUMNS } from './chunkOps'
import { documentPdfUrl } from './files'
import { shortHeadingPath, type ChunkStatusResult, type PublishedChunk } from './schema'

/**
 * 画一条已发布切片(表格行 + 可展开的全文行)。
 *
 * @param chunk 这一条切片。`retired` 为真表示退休行(`seq` 已还原成当初的编号)。
 * @param documentId 所属文档 id(图片与原件 PDF 的地址要用)。
 * @param onChanged 启用/禁用成功后的回执 —— 由上层就地改这一行,不整页重载。
 */
export function ChunkRow({
  chunk,
  documentId,
  onChanged,
}: {
  chunk: PublishedChunk
  documentId: string
  onChanged: (result: ChunkStatusResult) => void
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const retired = chunk.retired
  const heading = chunk.heading_path ? shortHeadingPath(chunk.heading_path.split(' > ')) : null
  const page = chunk.page_idx != null ? chunk.page_idx + 1 : null

  const act = async (what: 'disable' | 'enable') => {
    setBusy(true)
    try {
      const result = await apiPost<ChunkStatusResult>(`/api/document/chunks/${chunk.id}/${what}`)
      onChanged(result)
      pushToast(
        'success',
        what === 'disable' ? `Chunk ${chunk.seq} disabled` : `Chunk ${chunk.seq} enabled`,
        what === 'disable'
          ? 'Its vector was cleared, so neither retrieval leg can return it.'
          : 'Its vector was recomputed, so retrieval can return it again.',
      )
    } catch (error) {
      const code = error instanceof ApiError ? error.code : 'chunk_update_failed'
      pushToast('error', code, chunkFailureText(code))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <TR>
        <TD className="w-[1%] font-mono text-[12.5px] font-semibold">
          {retired ? <span className="text-ghost">{chunk.seq}</span> : chunk.seq}
        </TD>
        <TD className="max-w-[520px]">
          {heading && <div className="text-faint mb-0.5 truncate text-[11.5px]">{heading}</div>}
          <div className="truncate text-[13px]">{chunkPreview(chunk.content)}</div>
          {chunk.figure_count > 0 && (
            <div className="text-fainter mt-1 flex items-center gap-1.5 font-mono text-[10.5px]">
              <Images className="size-3" />
              {chunk.figure_count} figure{chunk.figure_count > 1 ? 's' : ''}
            </div>
          )}
        </TD>
        <TD className="text-faint font-mono text-[11px]">{page ?? '—'}</TD>
        <TD className="text-faint font-mono text-[11px]">{chunk.token_count ?? '—'}</TD>
        <TD>
          {chunk.embedded ? (
            <Badge tone="info">embedded</Badge>
          ) : (
            <span className="text-fainter font-mono text-[11px]">no vector</span>
          )}
        </TD>
        <TD>
          {retired ? (
            <Badge tone="danger">retired</Badge>
          ) : chunk.status === 'active' ? (
            <Badge tone="success">active</Badge>
          ) : (
            <Badge tone="neutral">disabled</Badge>
          )}
        </TD>
        <TD className="text-right">
          <div className="flex items-center justify-end gap-1.5">
            {retired ? (
              <span className="text-fainter font-mono text-[11px]">citations only</span>
            ) : (
              <RowAction status={chunk.status} busy={busy} onAct={act} />
            )}
            <button
              type="button"
              aria-label={open ? 'Collapse chunk' : 'Expand chunk'}
              aria-expanded={open}
              onClick={() => setOpen(!open)}
              className="text-fainter hover:bg-hover hover:text-body flex size-7 items-center justify-center rounded-[var(--radius-pill)] transition-all duration-150"
            >
              <ChevronDown
                className={cn('size-3.5 transition-transform duration-150', !open && '-rotate-90')}
              />
            </button>
          </div>
        </TD>
      </TR>

      {open && (
        <tr className="border-b border-[var(--border-soft)] last:border-0">
          <td colSpan={CHUNK_COLUMNS} className="bg-subtle px-[26px] py-4">
            <div className="text-fainter mb-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 font-mono text-[10.5px] tracking-[0.06em] uppercase">
              <span>chunk #{chunk.seq}</span>
              {page != null && <span>page {page}</span>}
              {chunk.token_count != null && <span>{chunk.token_count} tok</span>}
              <a
                href={documentPdfUrl(documentId, page ?? undefined)}
                target="_blank"
                rel="noreferrer"
                className="hover:text-body ml-auto inline-flex items-center gap-1 normal-case"
              >
                Source PDF
              </a>
            </div>
            {chunk.heading_path && (
              <div className="text-faint mb-2 text-[11.5px] leading-[1.5]">
                {chunk.heading_path}
              </div>
            )}
            <ChunkContent content={chunk.content} documentId={documentId} />
          </td>
        </tr>
      )}
    </>
  )
}

/** 一行只有一个动作,按 status 给(与 `DocumentsPage.RowAction` 同一个取舍)。 */
function RowAction({
  status,
  busy,
  onAct,
}: {
  status: PublishedChunk['status']
  busy: boolean
  onAct: (what: 'disable' | 'enable') => void
}) {
  if (status === 'active') {
    return (
      <Button size="sm" variant="danger" disabled={busy} onClick={() => onAct('disable')}>
        {busy ? <Loader2 className="animate-spin" /> : <EyeOff />}
        Disable
      </Button>
    )
  }
  return (
    <Button size="sm" variant="secondary" disabled={busy} onClick={() => onAct('enable')}>
      {busy ? <Loader2 className="animate-spin" /> : <RotateCw />}
      {busy ? 'Embedding…' : 'Enable'}
    </Button>
  )
}
