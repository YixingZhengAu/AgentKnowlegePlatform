/** 右侧面板插槽的 context —— 从 `AppLayout` 里拆出来的,原因很具体:
 *
 * `AppLayout` 要遍历 `DOMAINS` 生成导航,而域页面(如 S1 的校对页)要用 `useRightPanel`
 * 往右侧塞进度面板 —— 两边互相 import 就成环:
 * `domains/index → 域 module → 域页面 → AppLayout → domains/index`。
 * ESM 的环不会报编译错,只在运行时炸 `Cannot access 'DOMAINS' before initialization`
 * (Step 7b 的浏览器自测就是这么抓到的)。
 *
 * 拆开之后依赖是单向的:AppLayout 与各页面都只依赖本文件,本文件不认识任何域。
 */

import { createContext, useContext, useEffect, type ReactNode } from 'react'

export type PanelSlot = { title: string; content: ReactNode } | null

export const RightPanelContext = createContext<{ setPanel: (slot: PanelSlot) => void }>({
  setPanel: () => {},
})

/** 页面调用它把内容挂到右侧面板;依赖变化时自动替换,卸载时自动清空。 */
export function useRightPanel(title: string, content: ReactNode, deps: unknown[] = []) {
  const { setPanel } = useContext(RightPanelContext)
  useEffect(() => {
    setPanel({ title, content })
    return () => setPanel(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, ...deps])
}
