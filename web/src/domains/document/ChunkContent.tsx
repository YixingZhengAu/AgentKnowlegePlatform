/** 切片正文的渲染:把 `![](images/<sha>.jpg)` 换成真实截图,其余原样。
 *
 * 为什么不引 markdown 渲染器:切片正文里唯一的 markdown 语法就是这一种图片标记
 * (表格早在描述阶段被换成了 `[table description] …` 的纯文本)。
 * 为一条正则引一个渲染器,还得连带处理它对 HTML 的转义策略,不划算。
 */

import { figureUrl } from './files'

/** 描述阶段写进正文的图片标记,形如 `![](images/<sha256>.jpg)`。 */
const IMAGE_MARK = /!\[[^\]]*\]\((images\/[^)\s]+)\)/g

/** 渲染一段切片正文。
 *
 * @param content 切片的 `content` 原文。
 * @param documentId 拼图片地址用。
 */
export function ChunkContent({ content, documentId }: { content: string; documentId: string }) {
  const parts: React.ReactNode[] = []
  let cursor = 0

  for (const m of content.matchAll(IMAGE_MARK)) {
    const at = m.index
    if (at > cursor) parts.push(text(content.slice(cursor, at), parts.length))
    parts.push(
      <img
        key={`img-${parts.length}`}
        src={figureUrl(documentId, m[1])}
        alt="Figure from the source document"
        loading="lazy"
        className="bg-card my-2 max-h-[300px] w-full rounded-[var(--radius)] border border-[var(--border-soft)] object-contain"
      />,
    )
    cursor = at + m[0].length
  }
  if (cursor < content.length) parts.push(text(content.slice(cursor), parts.length))

  return <div className="text-[12.5px] leading-[1.7]">{parts}</div>
}

function text(chunk: string, key: number) {
  const trimmed = chunk.replace(/^\n+|\n+$/g, '')
  if (!trimmed) return null
  return (
    <p key={`t-${key}`} className="whitespace-pre-wrap">
      {trimmed}
    </p>
  )
}
