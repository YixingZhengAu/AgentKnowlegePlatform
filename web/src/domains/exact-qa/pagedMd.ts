/** 带页标记 markdown 的纯函数(切页 / 页锚点)—— 与渲染分开放,渲染文件只导出组件。
 *
 * 契约出处:`server/app/schemas/exact_qa.py` 的 `PAGE_MARKER_FMT`;
 * 抽取也靠这套标记给候选标页码(`services/exact_qa/extractor.py::split_by_pages`),
 * 所以校对时删掉标记是有后果的(校对页会提示)。
 */

/** 页标记(出处 `server/app/schemas/exact_qa.py` 的 `PAGE_MARKER_FMT`)。 */
export const PAGE_MARKER = /<!--\s*page:\s*(\d+)\s*-->/g

export type MdPage = { pageIdx: number; body: string }

/** 按页标记把文本切成页。没有标记(理论上不会)就整段算第 0 页,不能什么都不显示。 */
export function splitPages(text: string): MdPage[] {
  const pages: MdPage[] = []
  const marks = [...text.matchAll(PAGE_MARKER)]
  if (marks.length === 0) return [{ pageIdx: 0, body: text }]
  marks.forEach((m, i) => {
    const start = (m.index ?? 0) + m[0].length
    const end = i + 1 < marks.length ? marks[i + 1].index : text.length
    pages.push({ pageIdx: Number(m[1]), body: text.slice(start, end) })
  })
  return pages
}

/** 页锚点的 id —— 校对页两侧(PDF / Preview)用同一套页号,这里是 Preview 那一侧的落点。 */
export function pageAnchor(pageIdx: number): string {
  return `md-page-${pageIdx}`
}
