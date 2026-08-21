import { AlertTriangle, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import type { ApiError } from '@/api/client'
import { EmptyState } from '@/components/EmptyState'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

/** 列表页三态(loading / error / empty)的统一外壳,避免每个页面各写一遍。 */
export function DataState<T>({
  state,
  isEmpty,
  emptyIcon,
  emptyTitle,
  emptyDescription,
  children,
}: {
  state: { data: T | null; error: ApiError | null; loading: boolean; reload: () => void }
  isEmpty?: (data: T) => boolean
  emptyIcon: LucideIcon
  emptyTitle: string
  emptyDescription?: string
  children: (data: T) => ReactNode
}) {
  if (state.loading && !state.data) {
    return (
      <div className="flex flex-col gap-2 p-6">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-2/3" />
      </div>
    )
  }
  if (state.error) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title={state.error.code}
        description={state.error.message}
        action={
          <Button variant="secondary" size="sm" onClick={state.reload}>
            Retry
          </Button>
        }
      />
    )
  }
  if (!state.data || (isEmpty?.(state.data) ?? false)) {
    return <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDescription} />
  }
  return <>{children(state.data)}</>
}
