/** UI 改版自测的共用底座:路由清单 + 用无头 Chrome 把静态预览渲染出来。
 *
 * 为什么不用 Playwright MCP:那个浏览器实例常被别的会话占着(`Browser is already in use`),
 * 这里直接调 Playwright 已经下载好的 `chrome-headless-shell` 二进制,零依赖、可并发。
 *
 * 渲染对象是 `make demo` 产出的 `dist-demo/preview.html`(fixture 数据、零后端),
 * 所以截图与清单都不依赖 Postgres / OpenAI,任何时候都能重放。
 *
 * 关键手法:preview.html 是个 HTML 片段,这里在它前面塞一段引导脚本(设置 hash 路由)、
 * 后面塞一段探针脚本(等应用渲染完把结果写进 DOM),再整体写成临时文件交给 Chrome。
 * `--virtual-time-budget` 会把 setTimeout 的时间快进掉,所以「等 6 秒」实际只花几百毫秒。
 */

import { execFileSync } from 'node:child_process'
import { globSync } from 'node:fs'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
export const REPO = resolve(WEB, '..')
export const PREVIEW = join(WEB, 'dist-demo', 'preview.html')
const TMP = join(REPO, 'tmp', 'ui-tmp')

/** 虚拟时间轴上的两个时刻(ms):先做前置交互,再取数据/截图 */
const PREP_AT = 5000
const PROBE_AT = 7000

/** fixture 里的固定 id —— 与 `web/demo/fixtures.ts` 保持一致 */
const JOB = 'e1000000-0001-4a10-9f01-dddd00000001'
const AGENT = 'b726d168-53ed-4752-b204-a4b1fe0572f3'
const DOC = 'a1000000-0001-4a10-9f01-cccc00000001'

/** 改版要巡检的全部界面。`prep` 是渲染完、取数据前在页内跑的一段脚本,
 *  用来把「只有交互后才存在的形态」(例如收起右侧面板)也纳入基线。 */
export const ROUTES = [
  { key: 'chat', hash: '#/chat' },
  { key: 'agents', hash: '#/agents' },
  { key: 'agent-detail', hash: `#/agents/${AGENT}` },
  { key: 'ingest-exact-qa', hash: '#/ingest/exact-qa' },
  { key: 'proofread', hash: `#/ingest/exact-qa/documents/${DOC}/proofread` },
  { key: 'ingest-document', hash: '#/ingest/document' },
  { key: 'ingest-text2sql', hash: '#/ingest/text2sql' },
  { key: 'review', hash: `#/jobs/${JOB}/review` },
  {
    key: 'review-panel-hidden',
    hash: `#/jobs/${JOB}/review`,
    // 右侧面板收起态:Hide/Show 按钮的两种文案都要进基线,否则 Stage 3 改外壳时漏检
    prep: `[...document.querySelectorAll('button')].find(b => /^Hide /.test(b.textContent||''))?.click()`,
  },
  { key: 'settings', hash: '#/settings' },
  { key: 'styleguide', hash: '#/styleguide' },
]

function chromeBin() {
  const hits = globSync(
    join(
      process.env.HOME,
      'Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell',
    ),
  )
  if (!hits.length) throw new Error('找不到 chrome-headless-shell,先跑 npx playwright install chromium')
  return hits.sort().at(-1)
}

/** 把 preview.html 包成「指定路由 + 可选前置交互 + 可选探针」的临时页面。
 *  时间线(虚拟时间):0 设置路由 → 5s 跑 route.prep → 7s 探针取数 / 截图。 */
function pageFor(route, probe) {
  mkdirSync(TMP, { recursive: true })
  const preview = readFileSync(PREVIEW, 'utf8')
  const boot = `<script>location.hash = ${JSON.stringify(route.hash)}</script>\n`
  const prep = route.prep ? `\n<script>setTimeout(() => { ${route.prep} }, ${PREP_AT})</script>` : ''
  const file = join(TMP, `${route.key}.html`)
  writeFileSync(file, boot + preview + prep + (probe ?? ''))
  return file
}

/** 渲染一条路由。probe 有值就跑 `--dump-dom` 取 DOM,否则截图到 out。 */
export function render(route, { probe, out } = {}) {
  const file = pageFor(route, probe)
  const args = [
    '--headless',
    '--disable-gpu',
    '--no-sandbox',
    '--hide-scrollbars',
    '--force-device-scale-factor=1',
    '--window-size=1512,950',
    '--virtual-time-budget=12000',
    out ? `--screenshot=${out}` : '--dump-dom',
    `file://${file}`,
  ]
  return execFileSync(chromeBin(), args, { encoding: 'utf8', maxBuffer: 1 << 28, stdio: ['ignore', 'pipe', 'ignore'] })
}

/** 在页内等应用渲染完(含 fixture 的 220ms 延迟与轮询),再跑 body,结果写进 DOM 让 --dump-dom 带出来。 */
export function probeScript(body) {
  return `
<script>
  setTimeout(() => {
    let payload
    try { payload = JSON.stringify((() => { ${body} })()) } catch (e) { payload = JSON.stringify({ error: String(e) }) }
    const el = document.createElement('div')
    el.id = '__probe__'
    el.textContent = encodeURIComponent(payload)
    document.body.appendChild(el)
  }, ${PROBE_AT})
</script>`
}

/** 从 --dump-dom 的输出里取回探针结果。 */
export function readProbe(dom) {
  const m = dom.match(/<div id="__probe__">([^<]*)<\/div>/)
  if (!m) throw new Error('探针没有落地:页面可能白屏或崩了')
  return JSON.parse(decodeURIComponent(m[1]))
}
