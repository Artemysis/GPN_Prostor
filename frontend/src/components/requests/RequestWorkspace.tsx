import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileCheck2, MessageSquare, PieChart, Send } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress, Tabs } from '@/components/ui/misc'
import { StatusBadge } from '@/components/shared/badges'
import { useUiStore } from '@/lib/stores/uiStore'
import { formatMoney } from '@/lib/utils'
import { AiChat } from './AiChat'
import { TzBuilder } from './TzBuilder'
import { TzAnalysisPanel } from './TzAnalysisPanel'
import { ExportPanel } from './ExportPanel'

export function RequestWorkspace({ requestId, onTzCreated }: { requestId: string; onTzCreated?: () => void }) {
  const [tab, setTab] = useState('chat')
  const [pendingQuestion, setPendingQuestion] = useState<{ text: string; nonce: number } | null>(null)
  const queryClient = useQueryClient()
  const toast = useUiStore((s) => s.toast)

  const { data: request } = useQuery({
    queryKey: ['request', requestId],
    queryFn: () => api.getRequest(requestId),
    initialData: () => api.getRequest(requestId),
  })
  const { data: tz } = useQuery({
    queryKey: ['tz', requestId],
    queryFn: () => api.getTz(requestId),
    initialData: () => api.getTz(requestId),
  })
  const { data: templates = [] } = useQuery({ queryKey: ['templates'], queryFn: () => api.listTemplates() })

  if (!request) return null

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['request', requestId] })
    queryClient.invalidateQueries({ queryKey: ['tz', requestId] })
    queryClient.invalidateQueries({ queryKey: ['requests'] })
  }

  const createTz = (templateId: string, prefill = true) => {
    if (tz) return
    api.createTz(requestId, templateId, prefill)
    invalidate()
    onTzCreated?.()
    toast('ТЗ создано из шаблона', 'success')
  }

  const askAi = (text: string) => {
    setTab('chat')
    setPendingQuestion({ text, nonce: Date.now() })
  }

  const submit = () => {
    api.submitRequest(requestId)
    invalidate()
    toast('Заявка отправлена', 'success')
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-brand-800">{request.number}</span>
            <StatusBadge status={request.status} />
          </div>
          <h1 className="mt-0.5 truncate text-lg font-bold text-slate-900">{request.title}</h1>
          <p className="text-xs text-slate-400">
            {api.listCompanies().find((c) => c.company_id === request.company_id)?.name ?? 'подрядчик не выбран'} ·{' '}
            {api.listProducts().find((p) => p.product_id === request.product_id)?.product_name ?? 'продукт не выбран'} ·{' '}
            {formatMoney(request.cost_total, request.currency)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {tz && (
            <div className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2">
              <FileCheck2 className="h-4 w-4 text-brand-700" />
              <div>
                <p className="text-[10px] uppercase tracking-wide text-slate-400">готовность ТЗ</p>
                <div className="flex items-center gap-2">
                  <Progress value={tz.completeness_pct} className="w-28" />
                  <span className="text-sm font-bold text-slate-800">{tz.completeness_pct}%</span>
                </div>
              </div>
            </div>
          )}
          <Button onClick={submit} disabled={request.status === 'submitted' || !tz}>
            <Send className="h-4 w-4" />
            {request.status === 'submitted' ? 'Отправлена' : 'Отправить заявку'}
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-4 p-4">
        <div className="min-w-0 flex-1 overflow-y-auto pr-1">
          {!tz ? (
            <div className="space-y-3">
              <Card className="p-5">
                <p className="text-sm font-semibold text-slate-800">Выберите тип ТЗ</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  Шаблон можно выбрать вручную или принять рекомендацию ИИ из чата — она появится карточкой «Рекомендация шаблона ТЗ»
                </p>
                <div className="mt-4 grid grid-cols-2 gap-2.5 xl:grid-cols-3">
                  {templates.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => createTz(t.id)}
                      className="group rounded-xl border border-slate-200 bg-white p-3.5 text-left transition-colors hover:border-brand-400 hover:bg-brand-50/40"
                    >
                      <p className="text-sm font-semibold text-slate-800 group-hover:text-brand-900">{t.name}</p>
                      <p className="mt-1 line-clamp-2 text-xs text-slate-500">{t.description}</p>
                      <p className="mt-2 flex items-center gap-1 text-[11px] font-medium text-brand-700 opacity-0 transition-opacity group-hover:opacity-100">
                        <CheckCircle2 className="h-3 w-3" />
                        Создать ТЗ (с предзаполнением из чата)
                      </p>
                    </button>
                  ))}
                </div>
              </Card>
            </div>
          ) : (
            <TzBuilder requestId={requestId} tz={tz} />
          )}
        </div>

        <div className="flex w-[400px] shrink-0 flex-col gap-3">
          <Tabs
            items={[
              { value: 'chat', label: <span className="flex items-center justify-center gap-1.5"><MessageSquare className="h-3.5 w-3.5" />Чат</span> },
              { value: 'analysis', label: <span className="flex items-center justify-center gap-1.5"><PieChart className="h-3.5 w-3.5" />Анализ</span> },
              { value: 'export', label: <span className="flex items-center justify-center gap-1.5"><FileCheck2 className="h-3.5 w-3.5" />Документы</span> },
            ]}
            value={tab}
            onChange={setTab}
          />
          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === 'chat' && (
              <AiChat
                className="h-full"
                requestId={requestId}
                onApplied={invalidate}
                pendingQuestion={pendingQuestion}
              />
            )}
            {tab === 'analysis' && <TzAnalysisPanel requestId={requestId} onAskAi={askAi} />}
            {tab === 'export' && <ExportPanel requestId={requestId} />}
          </div>
        </div>
      </div>
    </div>
  )
}
