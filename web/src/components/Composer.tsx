/** 输入框:Enter 发送,Shift+Enter 换行,流式期间变成 Stop。
 *
 * Stop 不是装饰:它 abort 掉 fetch,后端会把这条消息按 `interrupted` 落库
 * (见 server/app/core/chat.py 的中断处理)。演示"中断了会怎样"就靠它。
 */

import { Send, Square } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'

export function Composer({
  onSend,
  onStop,
  streaming,
  disabled,
}: {
  onSend: (text: string) => void
  onStop: () => void
  streaming: boolean
  disabled?: boolean
}) {
  const [text, setText] = useState('')

  const submit = () => {
    if (!text.trim() || streaming) return
    onSend(text)
    setText('')
  }

  return (
    <div className="bg-card flex items-end gap-3 border-t px-6 py-4">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        rows={1}
        disabled={disabled}
        placeholder="Ask about warranty, installation or sales numbers…"
        className="bg-card focus:border-primary max-h-40 min-h-9 flex-1 resize-y rounded-[var(--radius)] border px-3 py-2 text-[14px] outline-none focus:ring-2 focus:ring-[var(--primary-soft)] disabled:cursor-not-allowed"
      />
      {streaming ? (
        <Button variant="secondary" onClick={onStop}>
          <Square />
          Stop
        </Button>
      ) : (
        <Button onClick={submit} disabled={disabled || !text.trim()}>
          <Send />
          Send
        </Button>
      )}
    </div>
  )
}
