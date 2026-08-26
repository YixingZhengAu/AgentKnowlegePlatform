/** 把一块区域变成"可以把文件拖进来"的投放区。
 *
 * 为什么单独抽一个 hook:拖放要处理的事比看起来多 ——
 * `dragenter`/`dragleave` 会在**子元素之间移动时也触发**,只靠这两个事件切换高亮态,
 * 鼠标经过卡片里的按钮就会闪。所以这里用计数器而不是布尔值。
 * 另外必须 `preventDefault` 掉 `dragover`,否则浏览器不认这是投放区,松手会**直接打开那个 PDF**
 * (整页被替换掉,用户以为程序崩了)。
 */

import { useRef, useState, type DragEvent } from 'react'

/** 从一次投放里挑出第一个可接受的文件。 */
function pick(list: FileList | null, accept: (f: File) => boolean): File | null {
  if (!list) return null
  for (const f of Array.from(list)) if (accept(f)) return f
  return null
}

/**
 * 让一个元素接受拖入的文件。
 *
 * @param accept 判断一个文件收不收(类型/后缀由调用方决定,这里不假设)。
 * @param onFile 收到第一个可接受的文件时调用。
 * @param onReject 拖进来的东西一个都不收时调用(给人话提示,别静默吞掉)。
 * @returns `{ dragging, handlers }` —— `dragging` 给高亮态用,`handlers` 直接摊到元素上。
 */
export function useFileDrop(
  accept: (file: File) => boolean,
  onFile: (file: File) => void,
  onReject?: () => void,
) {
  const [dragging, setDragging] = useState(false)
  // 🩸 用计数器而不是布尔:子元素间移动会成对触发 enter/leave,布尔值会让高亮闪烁
  const depth = useRef(0)

  const onDragEnter = (e: DragEvent) => {
    e.preventDefault()
    depth.current += 1
    // 只在真的拖着文件时亮起 —— 拖一段选中的文字进来不该有反应
    if (Array.from(e.dataTransfer.types).includes('Files')) setDragging(true)
  }

  const onDragOver = (e: DragEvent) => {
    // 不拦掉它,浏览器会把松手当成"打开这个文件",整页被 PDF 替换
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }

  const onDragLeave = (e: DragEvent) => {
    e.preventDefault()
    depth.current -= 1
    if (depth.current <= 0) {
      depth.current = 0
      setDragging(false)
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    depth.current = 0
    setDragging(false)
    const file = pick(e.dataTransfer.files, accept)
    if (file) onFile(file)
    else onReject?.()
  }

  return { dragging, handlers: { onDragEnter, onDragOver, onDragLeave, onDrop } }
}
