/** 带高亮的 SQL 编辑器(D4)—— **没有引入任何编辑器依赖**。
 *
 * 做法:一层 `<pre>` 画着色后的 token,一层完全透明的 `<textarea>` 盖在它上面接键盘。
 * 两层用同一份字体/字号/行高/内边距,所以字符逐个对齐;外层容器负责滚动,
 * 两层一起滚(textarea 是 `absolute inset-0`,高度跟着内容走,自己不滚)。
 *
 * 为什么不上 CodeMirror / Monaco:这一页要的只是"关键字能看出来、能改、能选中复制"。
 * 一个编辑器依赖会把前端体积和 `bootstrap.sh` 一起变复杂,而**面试要能解释每一行**。
 * 代价写清楚:没有括号匹配、没有自动缩进、没有列高亮 —— 这些这一页不需要。
 *
 * 着色规则本身在 `sqlTokens.ts`(纯模块)—— D5 的引用卡要用同一份配色画只读的最终 SQL。
 *
 * ⚠ 唯一的已知局限:超长的一行折行时,两层的折行位置理论上可能差一个字符
 * (同字体同宽度下实测一致)。模板 SQL 是**多行排版过**的文本,一行不会长到折行 ——
 * 排版由后端 `services/text2sql/sqltext.py` 落库前做掉,前端只负责忠实显示;
 * 但人可以在这里手打出一条超长单行,那时上面这条局限就成立了(可选中复制不受影响)。
 */

import { useMemo } from 'react'

import { cn } from '@/lib/utils'

import { SQL_TONE, tokenizeSql } from './sqlTokens'

export function SqlEditor({
  value,
  onChange,
  disabled,
  label,
}: {
  value: string
  onChange: (next: string) => void
  disabled?: boolean
  label: string
}) {
  const tokens = useMemo(() => tokenizeSql(value), [value])
  // 两层共用的排版类:改动其中任何一个数字都必须同时改两层,所以它只写一次
  const type = 'font-mono text-[12.5px] leading-[1.7] p-4 whitespace-pre-wrap break-words'

  return (
    <div className="bg-subtle focus-within:bg-background focus-within:ring-primary/12 max-h-[420px] overflow-auto rounded-[var(--radius-panel)] transition-all duration-150 focus-within:ring-4">
      <div className="relative min-h-[120px] w-full">
        <pre aria-hidden className={cn(type, 'm-0')}>
          {tokens.map((t, i) => (
            <span key={i} className={SQL_TONE[t.kind]}>
              {t.text}
            </span>
          ))}
          {/* 末尾补一个换行:光标停在最后一行时 pre 的高度不能比 textarea 矮 */}
          {'\n'}
        </pre>
        <textarea
          aria-label={label}
          spellCheck={false}
          disabled={disabled}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={cn(
            type,
            'caret-foreground absolute inset-0 h-full w-full resize-none border-0 bg-transparent text-transparent outline-none',
          )}
        />
      </div>
    </div>
  )
}
