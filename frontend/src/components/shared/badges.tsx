import { Badge } from '@/components/ui/badge'
import type { FilledBy, RequestStatus } from '@/lib/api'

export const statusLabels: Record<RequestStatus, string> = {
  draft: 'Черновик',
  submitted: 'Отправлена',
  deleted: 'Удалено',
}

export function StatusBadge({ status }: { status: RequestStatus }) {
  const variant = status === 'submitted' ? 'default' : status === 'deleted' ? 'danger' : 'slate'
  return <Badge variant={variant}>{statusLabels[status]}</Badge>
}

export function FilledByBadge({ value }: { value?: FilledBy }) {
  if (!value || value === 'manual') return null
  if (value === 'ai') return <Badge variant="ai">ИИ</Badge>
  return <Badge variant="mixed">ИИ + правки</Badge>
}
