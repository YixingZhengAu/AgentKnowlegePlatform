/** 把 dist-demo 的产物拼成一个自包含 HTML 片段(`make demo` 的第二步)。
 *
 * 产出 `dist-demo/preview.html`:只有 <title> + <style> + #root + <script type="module">,
 * 没有 <html>/<head>/<body> —— 这样既能直接丢到静态托管,也能被 Artifact 之类的
 * 「只吃页面内容、外壳由平台包」的托管方式直接用。
 * 字体已在构建时内联成 data URI,所以整页零外部请求(CSP 再严也能跑)。
 */

import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const OUT_DIR = 'dist-demo'
const ASSETS = join(OUT_DIR, 'assets')

const files = readdirSync(ASSETS)
const css = files.find((f) => f.endsWith('.css'))
const js = files.find((f) => f.endsWith('.js'))
if (!css || !js) throw new Error('dist-demo/assets 里没找到 css/js,先跑 vite build')

const cssText = readFileSync(join(ASSETS, css), 'utf8')
// 两处必须处理:
// 1. `</script` 会提前结束标签(字符串里多个反斜杠对 JS 无影响)
// 2. 非 ASCII 字符转成 \uXXXX —— 片段里没法声明 <meta charset>,
//    托管方按别的编码解就会出现 "·" 变 "Â·" 这种乱码(踩过)
const jsText = readFileSync(join(ASSETS, js), 'utf8')
  .replaceAll('</script', '<\\/script')
  .replace(/[^\x00-\x7f]/gu, (ch) =>
    [...ch].map((c) => '\\u' + c.codePointAt(0).toString(16).padStart(4, '0')).join(''),
  )

const html = `<title>Clenergy Knowledge Agent</title>
<style>
${cssText}
</style>
<div id="root"></div>
<script type="module">
${jsText}
</script>
`

const out = join(OUT_DIR, 'preview.html')
writeFileSync(out, html)
console.log(`[demo] ${out}  ${(html.length / 1024).toFixed(0)} KB`)
