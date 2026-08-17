import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { RequestWorkspace } from '@/components/requests/RequestWorkspace'

export default function RequestDetail() {
  const { id } = useParams<{ id: string }>()
  if (!id) return null
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 bg-white px-6 py-2.5">
        <Link to="/" className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-brand-800">
          <ArrowLeft className="h-3.5 w-3.5" />
          Все заявки
        </Link>
      </div>
      <div className="min-h-0 flex-1">
        <RequestWorkspace requestId={id} />
      </div>
    </div>
  )
}
