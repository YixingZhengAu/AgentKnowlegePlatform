/** 本域共用的两个请求小工具。
 *
 * `apiPut`:shared 层的 `client.ts` 没有 PUT(S0/S1 用不到),而它对域开发者是只读的 ——
 * 域内包一层就够了,不为一个方法去改公共契约文件。本域有三处 PUT
 * (`PUT /tables/{id}`、`PUT /intents/{id}/questions`、`PUT /non-data-faces`),
 * 所以它值得从页面里抽出来。
 *
 * `reason`:报错文案统一从 `ApiError` 拿(后端的 message 已经是给人看的英文,
 * 而且"连不上"这类业务结果根本不走异常),认不出来才兜底。
 */

import { ApiError, apiFetch } from '@/api/client'

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'PUT', body: JSON.stringify(body) })
}

export function reason(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback
}
