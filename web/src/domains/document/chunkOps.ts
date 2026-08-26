/** 切片管理页的纯逻辑:错误码文案、seq 空洞、正文预览。
 *
 * 刻意与 React 无关 —— 页面、行、重跑卡三处都要用同一套说法,
 * 尤其是错误码文案:同一个 code 在两个地方翻译成两句话是最容易发生的不一致。
 */

/** 表格的列数(gap 标记那一行要 `colSpan` 铺满)。改列的时候记得改这里。 */
export const CHUNK_COLUMNS = 7

/** 一行最多摆几个缺掉的 seq,超了折成 `+N more` —— 空洞可能有几十个。 */
const MAX_GAP_SHOWN = 8

/** 正文预览截多长(表格里只有一行的位置)。 */
const PREVIEW_CHARS = 180

/** 正文里的图片标记,预览时要去掉(出处 `ChunkContent.tsx` 的同一条正则)。 */
const IMAGE_MARK = /!\[[^\]]*\]\(images\/[^)\s]+\)/g

/** 禁用 / 启用 / 重跑失败时后端给的 code → 人话。
 *  出处 `server/app/api/document.py`,那边加一个 code 这里要跟着加。 */
export const CHUNK_FAILURE_TEXT: Record<string, string> = {
  chunk_already_disabled: 'This chunk is already disabled.',
  chunk_already_active: 'This chunk is already active.',
  chunk_retired: 'This chunk was retired by a later publish, so it can no longer be changed.',
  source_missing: 'The original file for this document is no longer available.',
  chunk_not_found: 'This chunk is no longer in the knowledge base.',
}

/**
 * 把后端 code 翻成一句可以直接摆到 toast 里的话。
 *
 * @param code `ApiError.code`,认不出来时也要给出一句人话。
 * @returns 一句完整的英文说明。
 */
export function chunkFailureText(code: string): string {
  return CHUNK_FAILURE_TEXT[code] ?? 'That did not work. Nothing was changed.'
}

/**
 * 闭区间 `[from, to]` 的整数序列 —— 两条相邻切片之间缺掉的那几个 seq。
 *
 * @param from 第一个缺号。
 * @param to 最后一个缺号(含)。
 * @returns 缺号数组;`from > to` 时为空。
 */
export function seqRange(from: number, to: number): number[] {
  const out: number[] = []
  for (let n = from; n <= to; n += 1) out.push(n)
  return out
}

/**
 * 空洞标记那一行的文案。
 *
 * seq 是发布时钉死的,审核里被驳回或被合并掉的那几条**不会**让后面的号往前挪 ——
 * 于是号码里留下的洞就是"这里原本有东西、被人拿掉了"的唯一痕迹。
 * 上下文扩展取的是 seq±1,读者要能看见它为什么会跳号。
 *
 * @param missing 缺掉的 seq,升序。
 * @returns 形如 `seq 1, 5 — removed during review`;`missing` 为空时返回空串。
 */
export function gapLabel(missing: number[]): string {
  if (missing.length === 0) return ''
  const shown = missing.slice(0, MAX_GAP_SHOWN).join(', ')
  const rest = missing.length - MAX_GAP_SHOWN
  const list = rest > 0 ? `${shown} +${rest} more` : shown
  return `seq ${list} — removed during review`
}

/**
 * 表格里那一行正文预览:去掉图片标记、压平换行、截断。
 *
 * @param content 切片正文原文。
 * @returns 单行纯文本,超长时以 `…` 收尾。
 */
export function chunkPreview(content: string): string {
  const flat = content.replace(IMAGE_MARK, ' ').replace(/\s+/g, ' ').trim()
  return flat.length > PREVIEW_CHARS ? `${flat.slice(0, PREVIEW_CHARS)}…` : flat
}
