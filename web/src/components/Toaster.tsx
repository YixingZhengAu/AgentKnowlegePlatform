import { X } from 'lucide-react'
import { useSyncExternalStore } from 'react'

import { cn } from '@/lib/utils'
import { dismissToast, getToasts, subscribeToasts, type ToastTone } from '@/lib/toast'

const TONE: Record<ToastTone, string> = {
  error: 'border-destructive/30 text-destructive',
  info: 'border-info/30 text-info',
  success: 'border-success/30 text-success',
}

export function Toaster() {
  const toasts = useSyncExternalStore(subscribeToasts, getToasts, getToasts)

  return (
    <div className="pointer-events-none fixed right-6 bottom-6 z-50 flex w-[360px] flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'bg-card pointer-events-auto flex items-start gap-3 rounded-[var(--radius-card)] border px-4 py-3 shadow-[var(--shadow-pop)]',
            TONE[t.tone],
          )}
        >
          <div className="min-w-0 flex-1">
            <div className="font-mono text-[12px] font-medium">{t.title}</div>
            {t.description && (
              <div className="text-secondary-foreground mt-1 text-[12px] break-words">
                {t.description}
              </div>
            )}
          </div>
          <button
            onClick={() => dismissToast(t.id)}
            className="text-muted-foreground hover:text-foreground"
            aria-label="Dismiss"
          >
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
