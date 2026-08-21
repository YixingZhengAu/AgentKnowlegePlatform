/** fetch 封装:后端错误体 -> ApiError -> 统一 toast。
 *
 * 后端错误体格式固定(server/app/core/errors.py):
 *   {"error": {"code": "...", "message": "...", "detail": ...}}
 * 前端只认这一个形状;认不出来的响应一律归到 http_error / network_error。
 */

// 开发环境走 Vite 代理(同源,见 vite.config.ts),所以默认空前缀。
// `import.meta.env?.` 的可选链不是多余的:scripts/smoke_sse.ts 用 Node 直接跑这份代码,
// 那边没有 Vite 注入的 env 对象。
const API_BASE = import.meta.env?.VITE_API_BASE ?? ''

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly detail: unknown

  constructor(code: string, message: string, status: number, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.detail = detail
  }
}

type ErrorBody = { error?: { code?: string; message?: string; detail?: unknown } }

/** 把非 2xx 响应翻译成 ApiError(响应体读不动也要给出可读的话)。 */
export async function toApiError(res: Response): Promise<ApiError> {
  let body: ErrorBody | null
  try {
    body = (await res.json()) as ErrorBody
  } catch {
    body = null
  }
  const err = body?.error
  return new ApiError(
    err?.code ?? 'http_error',
    err?.message ?? `Request failed with status ${res.status}`,
    res.status,
    err?.detail,
  )
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_BASE + path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch (cause) {
    // 网络层失败(后端没起、被断网):这里必须给一句人能看懂的话,
    // 否则界面上只会出现一个 "Failed to fetch"。
    throw new ApiError('network_error', 'Cannot reach the API server.', 0, String(cause))
  }
  if (!res.ok) throw await toApiError(res)
  return (await res.json()) as T
}

export { API_BASE }
