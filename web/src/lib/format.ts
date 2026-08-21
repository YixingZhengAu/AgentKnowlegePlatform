/** 展示格式化 —— 界面是英文单语(D5),locale 固定 en-AU(平台面向澳洲用户)。 */

const LOCALE = 'en-AU'

export function fmtDate(iso?: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(LOCALE, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function fmtDateTime(iso?: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(LOCALE, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fmtMs(ms?: number | null) {
  if (ms == null) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`
}

/** 成本后端给的是字符串/Decimal(numeric(10,6)),前端只负责显示,不做算术。 */
export function fmtUsd(v?: string | number | null) {
  if (v == null) return '—'
  const n = typeof v === 'string' ? Number(v) : v
  if (Number.isNaN(n)) return String(v)
  return `$${n.toFixed(6)}`
}

export function fmtTokens(usage?: Record<string, unknown> | null) {
  if (!usage) return '—'
  const p = usage.prompt_tokens ?? 0
  const c = usage.completion_tokens ?? 0
  return `${p} + ${c}`
}
