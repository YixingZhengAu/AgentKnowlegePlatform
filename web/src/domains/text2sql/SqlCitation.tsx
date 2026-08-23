/** D5 chat 里的问数引用 —— 一条 `sql` 引用怎么显示在助手气泡下面。
 *
 * 通用引用条只能说"命中了什么、多少分";问数命中要多说三件事,少一件就没法验:
 *
 *   1. **数据本身**(结论那句话是代码从这张表算出来的,不是模型写的);
 *   2. **最终 SQL**(可展开 + 复制:演示时"这个数怎么来的"要能当场贴到 MySQL 里跑);
 *   3. **执行闸做过什么**(`flags`:强制加了 LIMIT、行数被截断);
 *   4. **这一命中是不是踩线过的**(`needs_confirmation`:边距不足,照跑 top1)。
 *
 * 所以本域给 `citation_type='sql'` 登记了自己的渲染器(`module.ts` 的 `citations`),
 * 数据全在 `citation.extra` 里 —— 出处 `services/text2sql/runtime.py::citations`,
 * 它是刻意把结果集塞进引用的:**前端不该为了画这张表再发一次请求**
 * (那条 SQL 再跑一次未必是同一份数,而引用是要留档的)。
 *
 * `extra` 在 openapi 里是 `extra="allow"` 的宽松结构(见 `CitationExtra` 的 docstring),
 * 所以这里用几个窄取值函数读它 —— 与审核台读 jsonb payload 是同一套做法,不是手写 API 类型。
 */

import { Check, ChevronDown, ClipboardCopy, Database } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { MessageCitation } from '@/api/schema'
import { Badge } from '@/components/ui/badge'
import { Table, TD, TH, THead, TR } from '@/components/ui/table'
import { pushToast } from '@/lib/toast'
import { cn } from '@/lib/utils'

import { SQL_TONE, tokenizeSql } from './sqlTokens'

type Extra = Record<string, unknown>

function text(e: Extra, key: string): string {
  const v = e[key]
  return typeof v === 'string' ? v : ''
}

function num(e: Extra, key: string): number | null {
  const v = e[key]
  return typeof v === 'number' ? v : null
}

function list(e: Extra, key: string): unknown[] {
  const v = e[key]
  return Array.isArray(v) ? v : []
}

function flag(e: Extra, key: string): boolean {
  return e[key] === true
}

export function SqlCitationCard({ citation }: { citation: MessageCitation }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const extra = (citation.extra ?? {}) as Extra
  const cols = list(extra, 'cols').map(String)
  const rows = list(extra, 'rows').filter(Array.isArray) as unknown[][]
  const flags = list(extra, 'flags').map(String)
  const rowcount = num(extra, 'rowcount')
  const score = num(extra, 'score')
  // 检索是"踩线过的"(是问数问题,但 top1 与 top2 的边距不够):照跑 top1,但必须说出来。
  // 出处 `pipeline.answer` 的 `needs_confirmation` —— B8 的原话是"让人看见这题是踩线过的"
  const thin = flag(extra, 'needs_confirmation')
  const tokens = useMemo(() => tokenizeSql(citation.snippet ?? ''), [citation.snippet])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(citation.snippet ?? '')
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      // 剪贴板要权限(非 https 的场景会拒),失败就说清楚,别静默
      pushToast('error', 'copy_failed', 'The browser refused clipboard access.')
    }
  }

  return (
    <div className="mt-3.5 border-t border-[var(--border)] pt-3">
      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <span className="bg-kb-text2sql size-[7px] shrink-0 rounded-full" />
        <span className="text-fainter font-mono text-[11px]">[{citation.seq}]</span>
        <span className="min-w-0 flex-1 truncate text-[12.5px]">
          {text(extra, 'intent_summary') || 'Structured data'}
        </span>
        {text(extra, 'intent_code') && (
          <span className="text-faint font-mono text-[11px]">{text(extra, 'intent_code')}</span>
        )}
        {score != null && (
          <span className="text-faint shrink-0 font-mono text-[11px]">{score.toFixed(3)}</span>
        )}
      </div>

      {thin && (
        <p className="text-faint mb-2.5 text-[11.5px] leading-[1.6]">
          Matched on a thin margin — the next closest intent scored nearly the same. Worth
          checking this is the question you meant.
        </p>
      )}

      {/* 数据表格默认摊开:结论那句话就是从它算出来的,让人先看见数 */}
      {cols.length > 0 && (
        <div className="overflow-hidden rounded-[var(--radius)] border border-[var(--border-soft)]">
          <div className="max-h-[260px] overflow-auto">
            <Table>
              <THead>
                <TR>
                  {cols.map((c) => (
                    <TH key={c}>{c}</TH>
                  ))}
                </TR>
              </THead>
              <tbody>
                {rows.map((row, i) => (
                  <TR key={i}>
                    {row.map((cell, j) => (
                      <TD key={j} className="font-mono text-[11.5px] whitespace-nowrap">
                        {cell === null ? <span className="text-ghost">null</span> : String(cell)}
                      </TD>
                    ))}
                  </TR>
                ))}
              </tbody>
            </Table>
          </div>
          <div className="text-faint flex flex-wrap items-center gap-2 border-t border-[var(--border-soft)] px-3 py-2 font-mono text-[10.5px]">
            <Database className="size-3" />
            {rowcount != null ? `${rowcount} rows` : `${rows.length} rows`}
            {rowcount != null && rows.length < rowcount && ` · showing ${rows.length}`}
            {/* 闸动过手就要说出来,不能让人以为这是原始结果 */}
            {flags.map((f) => (
              <Badge key={f} tone="warning">
                {f}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={(e) => {
            // 气泡本身是"选中这条消息"的按钮,别让展开 SQL 顺带切了选中
            e.stopPropagation()
            setOpen((v) => !v)
          }}
          className="text-info flex items-center gap-1.5 text-[12px] hover:underline"
        >
          <ChevronDown
            className={cn('size-3.5 transition-transform duration-150', !open && '-rotate-90')}
          />
          {open ? 'Hide SQL' : 'Show the SQL that produced this'}
        </button>
        {open && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              void copy()
            }}
            className="text-faint hover:text-foreground ml-auto flex items-center gap-1.5 text-[11.5px] transition-colors"
          >
            {copied ? <Check className="size-3.5" /> : <ClipboardCopy className="size-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>
      {open && (
        // 着色用的是 D4 编辑器那份规则(`sqlTokens.ts`),文本一个字符没动 ——
        // Copy 拿到的就是执行过的原文
        <pre className="bg-subtle mt-2 overflow-auto rounded-[var(--radius)] px-4 py-3 font-mono text-[11px] leading-[1.7] break-words whitespace-pre-wrap">
          {tokens.map((t, i) => (
            <span key={i} className={SQL_TONE[t.kind]}>
              {t.text}
            </span>
          ))}
        </pre>
      )}
    </div>
  )
}
