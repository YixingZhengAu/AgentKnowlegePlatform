/** 极简 toast store:模块级状态 + 订阅,组件用 useSyncExternalStore 读。
 *
 * 刻意不引第三方 toast 库:全站只需要"失败弹一条"这一种行为,
 * 40 行自己写比装一个库更好解释,也不会跟设计 token 打架。
 */

export type ToastTone = 'error' | 'info' | 'success'

export type Toast = {
  id: number
  tone: ToastTone
  title: string
  description?: string
}

const AUTO_DISMISS_MS = 6000

let toasts: Toast[] = []
let seq = 0
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((fn) => fn())
}

export function subscribeToasts(fn: () => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function getToasts() {
  return toasts
}

export function dismissToast(id: number) {
  toasts = toasts.filter((t) => t.id !== id)
  emit()
}

export function pushToast(tone: ToastTone, title: string, description?: string) {
  const id = ++seq
  toasts = [...toasts, { id, tone, title, description }]
  emit()
  setTimeout(() => dismissToast(id), AUTO_DISMISS_MS)
  return id
}
