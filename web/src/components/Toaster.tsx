import { X } from 'lucide-react'
import { useSyncExternalStore } from 'react'

import { cn } from '@/lib/utils'
import { dismissToast, getToasts, subscribeToasts, type ToastTone } from '@/lib/toast'

const TONE: Record<ToastTone, string> = {
  error: 'text-destructive',
  info: 'text-info',
  success: 'text-success',
}

export function Toaster() {
  const toasts = useSyncExternalStore(subscribeToasts, getToasts, getToasts)

  return (
    <div className="pointer-events-none fixed right-6 bottom-6 z-50 flex w-[360px] flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'bg-card pointer-events-auto flex items-start gap-3 rounded-[var(--radius-panel)] border border-[var(--border)] px-[18px] py-[14px] shadow-[var(--shadow-pop)]',
            TONE[t.tone],
          )}
        >
          <div className="min-w-0 flex-1">
            <div className="font-mono text-[11.5px] font-medium tracking-[0.02em]">{t.title}</div>
            {t.description && (
              <div className="text-faint mt-1 text-[11.5px] leading-[1.5] break-words">
                {t.description}
              </div>
            )}
          </div>
          <button
            onClick={() => dismissToast(t.id)}
            className="text-fainter hover:text-foreground transition-colors duration-150"
            aria-label="Dismiss"
          >
            <X className="size-[15px]" strokeWidth={1.75} />
          </button>
        </div>
      ))}
    </div>
  )
}
