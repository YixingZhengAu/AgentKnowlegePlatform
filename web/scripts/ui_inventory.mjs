/** 交互清单基线 —— 视觉改版期间「只许改样子、不许改功能」的硬约束(UI-REDESIGN-PLAN 闸门 B)。
 *
 * 做法:把每条路由渲染出来,抓出全部可交互元素(button / a / input / textarea / select)的
 * 标签、类型、可访问文本、disabled、href 与顺序,存成 JSON 基线;之后每个 Stage 用
 * `--check` 与基线比对,**有一处差异就算这个 Stage 失败**。
 * 于是「不小心删了个按钮 / 改了按钮文案 / 让某个控件变成 disabled」这类事故会被机器拦住,
 * 而不是靠人盯截图。
 *
 * 用法:
 *   node scripts/ui_inventory.mjs            写基线到 tmp/ui-baseline/
 *   node scripts/ui_inventory.mjs --check    与基线比对,不一致则退出码 1
 * 前置:`make demo`(基线抓的是 dist-demo/preview.html)
 */

import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

import { probeScript, readProbe, render, REPO, ROUTES } from './ui_probe.mjs'

const DIR = join(REPO, 'tmp', 'ui-baseline')
const CHECK = process.argv.includes('--check')

// 在页内跑:按 DOM 顺序列出所有可交互元素的「身份」,外加一份结构计数。
// 结构计数是补漏用的:列表行做成 <tr onClick>(如 Agents 列表)时元素本身不是按钮,
// 光看可交互元素会漏掉「行少了一条」这种事故。
const COLLECT = `
  const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim()
  const label = (el) =>
    norm(el.getAttribute('aria-label') || el.textContent) ||
    norm(el.getAttribute('placeholder') || el.getAttribute('title') || el.value || '')
  const items = [...document.querySelectorAll('button, a, input, textarea, select, [role], [tabindex]')].map((el) => ({
    tag: el.tagName.toLowerCase(),
    role: el.getAttribute('role') || '',
    type: el.getAttribute('type') || '',
    text: label(el),
    disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
    href: el.getAttribute('href') || '',
  }))
  const count = (sel) => document.querySelectorAll(sel).length
  const structure = { tr: count('tr'), li: count('li'), table: count('table'), form: count('form'), label: count('label') }
  return { items, structure }
`

function collect(route) {
  const got = readProbe(render(route, { probe: probeScript(COLLECT) }))
  if (got.error) throw new Error(`${route.key}: ${got.error}`)
  return {
    route: route.key,
    hash: route.hash,
    count: got.items.length,
    structure: got.structure,
    items: got.items,
  }
}

mkdirSync(DIR, { recursive: true })
let failed = 0
for (const route of ROUTES) {
  const file = join(DIR, `${route.key}.json`)
  const now = JSON.stringify(collect(route), null, 2) + '\n'
  if (!CHECK) {
    writeFileSync(file, now)
    console.log(`[baseline] ${route.key.padEnd(20)} ${JSON.parse(now).count} interactive elements`)
    continue
  }
  if (!existsSync(file)) {
    console.error(`[MISSING]  ${route.key} 没有基线,先不带 --check 跑一次`)
    failed++
    continue
  }
  const was = readFileSync(file, 'utf8')
  if (was === now) {
    console.log(`[ok]       ${route.key.padEnd(20)} ${JSON.parse(now).count} interactive elements`)
    continue
  }
  failed++
  console.error(`[DIFF]     ${route.key}`)
  for (const line of diffOf(JSON.parse(was), JSON.parse(now))) console.error(`           ${line}`)
}

const diffOf = (a, b) => diff(a.items, b.items, a.structure, b.structure)

/** 按位置逐条比,只报不同的那几条(整份 JSON diff 读起来太吵)。 */
function diff(a, b, sa, sb) {
  const out = []
  for (const k of Object.keys(sa ?? {})) if (sa[k] !== sb[k]) out.push(`结构 ${k} ${sa[k]} -> ${sb[k]}`)
  if (a.length !== b.length) out.push(`数量 ${a.length} -> ${b.length}`)
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = JSON.stringify(a[i] ?? null)
    const y = JSON.stringify(b[i] ?? null)
    if (x !== y) out.push(`#${i}\n             was ${x}\n             now ${y}`)
  }
  return out.slice(0, 12)
}

if (failed) {
  console.error(`\n${failed} 条路由与基线不一致 —— 这一 Stage 不能通过。`)
  process.exit(1)
}
console.log(CHECK ? '\n交互清单与基线完全一致。' : `\n基线已写入 ${DIR}(${readdirSync(DIR).length} 个文件)`)
