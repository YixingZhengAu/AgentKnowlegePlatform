/** 只读 GET 的取数 hook。
 *
 * 刻意不引 react-query:S0 需要的只有 loading / error / reload / 轮询四件事,
 * 自己写 60 行比装一个库更好在面试里讲清"数据是怎么流的"。
 *
 * 两个 Step 7 加上来的能力:
 * - `refetchInterval`:Job 进度条靠它轮询。它可以是**一个读当前数据的函数** ——
 *   "任务到终态就停轮询"这个判断必须看到刚拿回来的数据,写成常量做不到
 *   (常量要在调用 useApi 之前算,那时数据还没回来)。函数返回 null 就停。
 * - `path` 可以为 `null`:hook 不能条件调用,但"这次不该取数"是常态
 *   (比如 trace 面板还没有 message_id),用 null 表达比造一个假 path 干净
 */

import { useCallback, useEffect, useState } from 'react'

import { ApiError, apiFetch } from './client'
import { pushToast } from '@/lib/toast'

export type ApiState<T> = {
  data: T | null
  error: ApiError | null
  loading: boolean
  reload: () => void
}

export type RefetchInterval<T> = number | null | ((data: T | null) => number | null)

export function useApi<T>(
  path: string | null,
  opts?: { toastOnError?: boolean; refetchInterval?: RefetchInterval<T> },
): ApiState<T> {
  const [tick, setTick] = useState(0)
  const toastOnError = opts?.toastOnError ?? true
  const refetchInterval = opts?.refetchInterval ?? null

  // key = 这次请求的身份。loading 由 "已装载的 key ?= 当前 key" 推导出来,
  // 不在 effect 里同步 setState(那会多一轮渲染,新版 react-hooks 规则也会直接报错)。
  const key = `${path ?? ''}#${tick}`
  const [result, setResult] = useState<{ key: string; data: T | null; error: ApiError | null }>({
    key: '',
    data: null,
    error: null,
  })

  useEffect(() => {
    if (path === null) return
    // 卸载/换 path 后不再 setState:请求慢时切页不会报"更新已卸载组件"
    let cancelled = false
    apiFetch<T>(path)
      .then((data) => {
        if (!cancelled) setResult({ key, data, error: null })
      })
      .catch((error: ApiError) => {
        if (cancelled) return
        setResult({ key, data: null, error })
        if (toastOnError) pushToast('error', error.code, error.message)
      })
    return () => {
      cancelled = true
    }
  }, [key, path, toastOnError])

  // 轮询:间隔算出来是 null 就不装定时器(任务到终态后接口彻底安静)。
  // 依赖里放的是算出来的数字,所以每次渲染给个新函数也不会重装定时器。
  const interval =
    typeof refetchInterval === 'function' ? refetchInterval(result.data) : refetchInterval
  useEffect(() => {
    if (path === null || !interval) return
    const id = setInterval(() => setTick((n) => n + 1), interval)
    return () => clearInterval(id)
  }, [path, interval])

  const reload = useCallback(() => setTick((n) => n + 1), [])
  return {
    data: result.data,
    error: result.error,
    loading: path !== null && result.key !== key,
    reload,
  }
}
