import { Badge } from '@/components/ui/badge'

/** 状态 -> 语义色的唯一映射(审核台的 approved/rejected、trace 的 ok/error 都走这里)。 */
const TONE: Record<string, 'success' | 'danger' | 'info' | 'neutral' | 'navy'> = {
  ok: 'success',
  active: 'success',
  completed: 'success',
  approved: 'success',
  published: 'navy',
  error: 'danger',
  failed: 'danger',
  rejected: 'danger',
  running: 'info',
  edited: 'info',
  interrupted: 'neutral',
  pending: 'neutral',
  archived: 'neutral',
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={TONE[status] ?? 'neutral'}>{status}</Badge>
}
