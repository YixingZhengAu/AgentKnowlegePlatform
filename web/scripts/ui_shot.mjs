/** 视觉验收截图 —— UI-REDESIGN-PLAN 闸门 C。
 *
 * 把同一批路由在 1512×950(演示用的笔记本尺寸)下逐条截图,按 Stage 分目录存放,
 * 于是「这一步到底改了哪些像素」可以和上一 Stage 并排看。
 *
 * 用法:node scripts/ui_shot.mjs <stage>   -> tmp/ui-shots/<stage>/<route>.png
 * 前置:`make demo`
 */

import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

import { render, REPO, ROUTES } from './ui_probe.mjs'

const stage = process.argv[2]
if (!stage) {
  console.error('用法: node scripts/ui_shot.mjs <stage>   例如 00-before')
  process.exit(1)
}
const dir = join(REPO, 'tmp', 'ui-shots', stage)
mkdirSync(dir, { recursive: true })

for (const route of ROUTES) {
  const out = join(dir, `${route.key}.png`)
  render(route, { out })
  console.log(`[shot] ${route.key.padEnd(20)} -> ${out}`)
}
