/** 只读 GET 的取数 hook。
 *
 * 刻意不引 react-query:S0 需要的只有 loading / error / reload 三个状态,
 * 自己写 40 行比装一个库更好在面试里讲清"数据是怎么流的"。
 * Step 7 的 Job 轮询会在这里加一个 `refetchInterval`,不需要换实现。
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

export function useApi<T>(path: string, opts?: { toastOnError?: boolean }): ApiState<T> {
  const [tick, setTick] = useState(0)
  const toastOnError = opts?.toastOnError ?? true

  // key = 这次请求的身份。loading 由 "已装载的 key ?= 当前 key" 推导出来,
  // 不在 effect 里同步 setState(那会多一轮渲染,新版 react-hooks 规则也会直接报错)。
  const key = `${path}#${tick}`
  const [result, setResult] = useState<{ key: string; data: T | null; error: ApiError | null }>({
    key: '',
    data: null,
    error: null,
  })

  useEffect(() => {
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

  const reload = useCallback(() => setTick((n) => n + 1), [])
  return {
    data: result.data,
    error: result.error,
    loading: result.key !== key,
    reload,
  }
}
