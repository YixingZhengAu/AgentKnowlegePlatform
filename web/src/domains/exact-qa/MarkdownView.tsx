/** 解析文本的渲染视图 —— 校对页右侧的 Preview。
 *
 * 三件事值得说明:
 *
 * 1. **必须允许原始 HTML**(`rehype-raw`):MinerU 把表格还原成 `<table>`、上下标还原成
 *    `<sub>`,不渲染 HTML 的话表格会变成一坨尖括号,校对就无从下手。
 *    内容来源是本系统自己的解析产物(不是用户粘贴的任意 HTML),这是这个决定的前提。
 * 2. **按页标记切块渲染**:`<!-- page: N -->` 是 HTML 注释,渲染时会被丢掉 ——
 *    可页码恰恰是校对时最需要的坐标。所以先按标记切开,每页自己一块并带 `id`,
 *    这样"跳到第 N 页"在 Preview 里也成立(锚点滚动),不只在 PDF 那一侧。
 * 3. 公式仍是 `$...$` 原文:S1 不引 KaTeX —— 校对关心的是"字有没有抄错",
 *    而不是公式排得好不好看(引了反而看不见原始字符)。
 */

import Markdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'

import { cn } from '@/lib/utils'

import { pageAnchor, splitPages } from './pagedMd'

const MD_COMPONENTS = {
  h1: (p: object) => (
    <h2 className="font-display mt-6 text-[17px] font-bold tracking-[-0.01em]" {...p} />
  ),
  h2: (p: object) => <h3 className="font-display mt-5 text-[15px] font-bold" {...p} />,
  h3: (p: object) => <h4 className="font-display mt-4 text-[13.5px] font-semibold" {...p} />,
  p: (p: object) => <p className="mt-2.5 text-[13.5px] leading-[1.75]" {...p} />,
  ul: (p: object) => (
    <ul className="mt-2.5 list-disc pl-5 text-[13.5px] leading-[1.75] marker:text-ghost" {...p} />
  ),
  ol: (p: object) => (
    <ol className="mt-2.5 list-decimal pl-5 text-[13.5px] leading-[1.75] marker:text-ghost" {...p} />
  ),
  blockquote: (p: object) => (
    <blockquote className="border-l-accent text-faint mt-3 border-l-[3px] pl-3.5" {...p} />
  ),
  code: (p: object) => (
    <code
      className="bg-subtle rounded-[var(--radius-kbd)] px-[5px] py-px font-mono text-[12px]"
      {...p}
    />
  ),
  // 表格可能很宽:让它在自己的容器里横向滚动,不要把整页撑出横向滚动条
  table: (p: object) => (
    <div className="mt-4 overflow-x-auto rounded-[var(--radius)] border border-[var(--border)]">
      <table
        className="w-full border-collapse text-[12px] [&_td]:border-t [&_td]:border-[var(--border-soft)] [&_td]:px-3 [&_td]:py-1.5 [&_th]:bg-subtle [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-semibold"
        {...p}
      />
    </div>
  ),
  img: (p: object) => (
    // 图片走文件服务(URL 已由后端改写);显示不出来时要看得见是哪一张,所以留 alt
    <img
      className="bg-subtle mt-4 max-w-full rounded-[var(--radius)] border border-[var(--border)]"
      loading="lazy"
      {...p}
    />
  ),
}

export function MarkdownView({ text, className }: { text: string; className?: string }) {
  const pages = splitPages(text)
  return (
    <div className={cn('flex max-w-[680px] flex-col gap-7', className)}>
      {pages.map((page) => (
        <section key={page.pageIdx} id={pageAnchor(page.pageIdx)} className="scroll-mt-4">
          <div className="text-fainter mb-2 font-mono text-[10.5px] tracking-[0.06em] uppercase">
            page {page.pageIdx + 1}
          </div>
          <div className="border-t border-[var(--border-soft)] pt-3">
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={MD_COMPONENTS}>
              {page.body}
            </Markdown>
          </div>
        </section>
      ))}
    </div>
  )
}
