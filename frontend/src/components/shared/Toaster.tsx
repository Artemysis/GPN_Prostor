import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { useUiStore } from '@/lib/stores/uiStore'
import { cn } from '@/lib/utils'

const icons = {
  success: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
  error: <AlertTriangle className="h-4 w-4 text-red-500" />,
  info: <Info className="h-4 w-4 text-brand-600" />,
}

export function Toaster() {
  const { toasts, dismiss } = useUiStore()
  return (
    <div className="fixed bottom-4 right-4 z-[100] flex w-80 flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'flex items-start gap-2.5 rounded-xl border bg-white px-4 py-3 text-sm shadow-card',
            t.kind === 'error' ? 'border-red-200' : t.kind === 'success' ? 'border-emerald-200' : 'border-brand-100',
          )}
        >
          {icons[t.kind]}
          <span className="flex-1 text-slate-700">{t.message}</span>
          <button onClick={() => dismiss(t.id)} className="text-slate-400 hover:text-slate-600">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}
