/** 切片表:按 `seq` 排的正式行 + **看得见的号码空洞** + 退休行分区。
 *
 * 🩸 **空洞不能悄悄合上**。`seq` 在发布那一刻就钉死了(`chunks` 的 UNIQUE(doc_id, seq)
 * 允许留空洞),审核里被驳回或被「Merge with next」吃掉的那几条不会让后面的号往前挪。
 * 于是列表里就会出现 0, 2, 3, 4, 6 —— 这不是 bug,是"这里原本有东西、被人拿掉了"的
 * 唯一痕迹。检索时的上下文扩展取的是 seq±1,读者必须看得见它为什么会跳号,
 * 所以缺号在两行之间单独占一条细线,而不是靠"自己数"。
 */

import { Minus } from 'lucide-react'
import type { ReactNode } from 'react'

import { Table, TH, THead, TR } from '@/components/ui/table'

import { ChunkRow } from './ChunkRow'
import { CHUNK_COLUMNS, gapLabel, seqRange } from './chunkOps'
import type { ChunkStatusResult, PublishedChunk } from './schema'

/**
 * 画整张切片表。
 *
 * @param items 后端按 `seq` 升序给的一整份(退休行 seq 为负,所以排在最前面)。
 * @param documentId 所属文档 id。
 * @param onChanged 某一行启用/禁用成功后的回执。
 */
export function ChunkTable({
  items,
  documentId,
  onChanged,
}: {
  items: PublishedChunk[]
  documentId: string
  onChanged: (result: ChunkStatusResult) => void
}) {
  const retired = items.filter((c) => c.retired)
  const live = items.filter((c) => !c.retired)

  const rows: ReactNode[] = []
  // 期望的下一个号:从 0 起,每画一行就往后推一格;对不上就是中间有洞
  let expected = 0
  for (const chunk of live) {
    if (chunk.seq > expected) {
      rows.push(<GapRow key={`gap-${expected}`} missing={seqRange(expected, chunk.seq - 1)} />)
    }
    expected = chunk.seq + 1
    rows.push(
      <ChunkRow key={chunk.id} chunk={chunk} documentId={documentId} onChanged={onChanged} />,
    )
  }

  return (
    <Table>
      <THead>
        <TR>
          <TH>Seq</TH>
          <TH>Chunk</TH>
          <TH>Page</TH>
          <TH>Tokens</TH>
          <TH>Vector</TH>
          <TH>Status</TH>
          <TH />
        </TR>
      </THead>
      <tbody>
        {rows}
        {retired.length > 0 && (
          <>
            <SectionRow>
              Retired by a later publish — kept only so citations in older answers still resolve.
              They are out of the index and cannot be re-enabled.
            </SectionRow>
            {retired.map((chunk) => (
              <ChunkRow
                key={chunk.id}
                chunk={chunk}
                documentId={documentId}
                onChanged={onChanged}
              />
            ))}
          </>
        )}
      </tbody>
    </Table>
  )
}

/** 两行之间那条细线:哪几个号在审核里被拿掉了。 */
function GapRow({ missing }: { missing: number[] }) {
  return (
    <tr className="border-b border-[var(--border-soft)]">
      <td colSpan={CHUNK_COLUMNS} className="px-4 py-1.5">
        <div className="text-fainter flex items-center gap-2.5 font-mono text-[10.5px]">
          <Minus className="size-3 shrink-0" />
          <span className="shrink-0">{gapLabel(missing)}</span>
          <span className="h-px flex-1 bg-[var(--border-soft)]" />
        </div>
      </td>
    </tr>
  )
}

/** 退休分区的说明行。 */
function SectionRow({ children }: { children: ReactNode }) {
  return (
    <tr className="border-b border-[var(--border-soft)]">
      <td colSpan={CHUNK_COLUMNS} className="bg-subtle px-4 py-2">
        <div className="text-faint text-[11.5px] leading-[1.5]">{children}</div>
      </td>
    </tr>
  )
}
