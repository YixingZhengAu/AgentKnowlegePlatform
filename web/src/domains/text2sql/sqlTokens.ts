/** SQL 高亮的分词器 —— D4 的编辑器(`SqlEditor.tsx`)与 D5 的引用卡
 *  (`SqlCitation.tsx`)共用同一份着色规则,所以它住在一个纯模块里
 *  (组件文件里只导出组件,否则 Vite 快速刷新会退化成整页重载)。
 *
 *  高亮只认三类东西:关键字 / 字面量(字符串与数字)/ 注释。够读了,不做语法分析。
 */

const KEYWORDS = new Set(
  (
    'select distinct from where group by order having limit offset join inner left right outer ' +
    'full cross on as and or not in is null like between case when then else end union all ' +
    'asc desc count sum avg min max coalesce cast date interval day month year current_date ' +
    'with exists over partition row_number date_format date_sub date_add now'
  ).split(' '),
)

export type SqlToken = { text: string; kind: 'kw' | 'lit' | 'comment' | 'plain' }

/** 纯函数分词 —— 与渲染分开,便于一眼看懂。 */
export function tokenizeSql(sql: string): SqlToken[] {
  const out: SqlToken[] = []
  // 一个正则四个分支:行注释 / 块注释 / 字符串 / 数字;其余按单词切
  const re = /(--[^\n]*|\/\*[\s\S]*?\*\/)|('(?:[^']|'')*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z_0-9]*)/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(sql)) !== null) {
    if (m.index > last) out.push({ text: sql.slice(last, m.index), kind: 'plain' })
    if (m[1]) out.push({ text: m[1], kind: 'comment' })
    else if (m[2] || m[3]) out.push({ text: m[2] ?? m[3], kind: 'lit' })
    else if (m[4])
      out.push({ text: m[4], kind: KEYWORDS.has(m[4].toLowerCase()) ? 'kw' : 'plain' })
    last = m.index + m[0].length
  }
  if (last < sql.length) out.push({ text: sql.slice(last), kind: 'plain' })
  return out
}

export const SQL_TONE: Record<SqlToken['kind'], string> = {
  kw: 'text-primary font-semibold',
  lit: 'text-success',
  comment: 'text-ghost italic',
  plain: '',
}
