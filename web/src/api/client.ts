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
  // 204 没有响应体(DELETE 会走到这里),res.json() 会抛 —— 不能无条件解析
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** 写操作:body 自动 JSON 化。返回类型与 GET 一样由调用方标注(仍来自生成的契约类型)。 */
export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
}

/** 文件上传(multipart)。
 *
 * **刻意不走 apiFetch**:那里无条件设了 `Content-Type: application/json`,
 * 而 multipart 的 Content-Type 必须由浏览器生成(它要往里塞 boundary)——
 * 手写这个头是上传最经典的一个坑,后端会收到一个解不开的 body。
 */
export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_BASE + path, { method: 'POST', body: form })
  } catch (cause) {
    throw new ApiError('network_error', 'Cannot reach the API server.', 0, String(cause))
  }
  if (!res.ok) throw await toApiError(res)
  return (await res.json()) as T
}

export function apiDelete(path: string): Promise<void> {
  return apiFetch<void>(path, { method: 'DELETE' })
}

export { API_BASE }
