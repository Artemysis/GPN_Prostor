import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, FileCheck2, MessageSquare, PencilLine, PieChart, Send } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress, Tabs } from '@/components/ui/misc'
import { Modal } from '@/components/ui/modal'
import { StatusBadge } from '@/components/shared/badges'
import { useUiStore } from '@/lib/stores/uiStore'
import { cn, formatMoney } from '@/lib/utils'
import { findMissingRequiredFields } from '@/lib/api/drafts'
import { AiChat } from './AiChat'
import { TzBuilder } from './TzBuilder'
import { TzAnalysisPanel } from './TzAnalysisPanel'
import { ExportPanel } from './ExportPanel'
import { RequestHeaderForm } from './RequestHeaderForm'

export function RequestWorkspace({ requestId, onTzCreated }: { requestId: string; onTzCreated?: () => void }) {
  const [tab, setTab] = useState('chat')
  const [pendingQuestion, setPendingQuestion] = useState<{ text: string; nonce: number } | null>(null)
  const [headerOpen, setHeaderOpen] = useState(false)
  const [creatingTz, setCreatingTz] = useState(false)
  const [creatingWithAi, setCreatingWithAi] = useState(false)
  const [chosenTemplateId, setChosenTemplateId] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const toast = useUiStore((s) => s.toast)

  const { data: request } = useQuery({
    queryKey: ['request', requestId],
    queryFn: () => api.getRequest(requestId),
  })
  const { data: tz } = useQuery({
    queryKey: ['tz', requestId],
    queryFn: () => api.getTz(requestId),
  })
  const { data: templates = [] } = useQuery({ queryKey: ['templates'], queryFn: () => api.listTemplates() })
  const { data: companies = [] } = useQuery({ queryKey: ['companies'], queryFn: () => api.listCompanies(), staleTime: Infinity })
  const { data: products = [] } = useQuery({ queryKey: ['products'], queryFn: () => api.listProducts(), staleTime: Infinity })
  const { data: tzTemplate } = useQuery({
    queryKey: ['template', tz?.template_id],
    queryFn: () => api.getTemplate(tz!.template_id),
    enabled: Boolean(tz),
    staleTime: Infinity,
  })

  if (!request) return null

  const missingFields =
    tz && tzTemplate ? findMissingRequiredFields(tzTemplate.blocks_schema.blocks, tz.payload, tz.stages) : []

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['request', requestId] })
    queryClient.invalidateQueries({ queryKey: ['tz', requestId] })
    queryClient.invalidateQueries({ queryKey: ['requests'] })
  }

  // prefill=false — ручной выбор шаблона: пустой конструктор для заполнения человеком.
  // ИИ-предзаполнение — только через чат (onCreateTz из карточки рекомендации ИИ).
  const createTz = (templateId: string, prefill = false) => {
    if (tz || creatingTz) return
    setChosenTemplateId(templateId) // закрепляем выбор цветом
    setCreatingTz(true)
    setCreatingWithAi(prefill)
    void api
      .createTz(requestId, templateId, prefill)
      .then(() => {
        invalidate()
        onTzCreated?.()
        toast(prefill ? 'ТЗ создано с ИИ-черновиком' : 'ТЗ создано — заполните блоки вручную', 'success')
      })
      .finally(() => {
        setCreatingTz(false)
        setCreatingWithAi(false)
      })
  }

  const askAi = (text: string) => {
    setTab('chat')
    setPendingQuestion({ text, nonce: Date.now() })
  }

  const submit = () => {
    void api.submitRequest(requestId).then(() => {
      invalidate()
      toast('Заявка отправлена', 'success')
    })
  }

  return (
    <div className="flex min-h-0 flex-col xl:h-full">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 xl:px-6 xl:py-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-brand-800">{request.number}</span>
            <StatusBadge status={request.status} />
          </div>
          <h1 className="mt-0.5 truncate text-base font-bold text-slate-900 xl:text-lg">{request.title}</h1>
          <p className="truncate text-xs text-slate-400">
            {companies.find((c) => c.company_id === request.company_id)?.name ?? 'исполнитель не выбран'} ·{' '}
            {products.find((p) => p.product_id === request.product_id)?.product_name ?? 'продукт не выбран'} ·{' '}
            {formatMoney(request.cost_total, request.currency)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 xl:gap-3">
          {tz && (
            <div className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 xl:px-3.5 xl:py-2">
              <FileCheck2 className="h-4 w-4 shrink-0 text-brand-700" />
              <div>
                <p className="text-[10px] uppercase tracking-wide text-slate-400">готовность ТЗ</p>
                <div className="flex items-center gap-2">
                  <Progress value={tz.completeness_pct} className="w-24 xl:w-28" />
                  <span className="text-sm font-bold text-slate-800">{tz.completeness_pct}%</span>
                </div>
              </div>
            </div>
          )}
          <Button
            variant="outline"
            onClick={() => setHeaderOpen(true)}
            disabled={request.status === 'submitted'}
            title={request.status === 'submitted' ? 'Заявка отправлена — редактирование недоступно' : 'Редактировать шапку заявки'}
          >
            <PencilLine className="h-4 w-4" />
            Изменить шапку
          </Button>
          <Button
            onClick={submit}
            disabled={request.status === 'submitted' || !tz || missingFields.length > 0}
            title={missingFields.length > 0 ? `Не заполнены обязательные поля:\n${missingFields.map((m) => m.label).join('\n')}` : undefined}
          >
            <Send className="h-4 w-4" />
            {request.status === 'submitted' ? 'Отправлена' : 'Отправить заявку'}
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 xl:flex-row">
        <div className="min-w-0 flex-1 xl:overflow-y-auto xl:pr-1">
          {!tz ? (
            <div className="space-y-3">
              <Card className="p-5">
                <p className="text-sm font-semibold text-slate-800">Выберите тип ТЗ</p>
                <p className="mt-0.5 text-xs text-slate-500">
                  Шаблон можно выбрать вручную или принять рекомендацию ИИ из чата — она появится карточкой «Рекомендация шаблона ТЗ»
                </p>
                {creatingTz && (
                  <div className="mt-3 space-y-1.5 rounded-lg bg-brand-50/60 px-3 py-2">
                    <p className="text-[11px] font-medium text-brand-800">
                      {creatingWithAi ? 'Создаём ТЗ с ИИ-предзаполнением…' : 'Создаём ТЗ…'}
                    </p>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
                      <div className="h-full w-1/3 animate-[progress-slide_1.4s_ease-in-out_infinite] rounded-full bg-brand-600" />
                    </div>
                  </div>
                )}
                <div className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
                  {templates.map((t) => {
                    const isSelected = t.id === chosenTemplateId
                    return (
                      <button
                        key={t.id}
                        onClick={() => createTz(t.id)}
                        disabled={creatingTz}
                        className={cn(
                          'group rounded-xl border p-3.5 text-left transition-colors disabled:opacity-100',
                          isSelected
                            ? 'border-emerald-400 bg-emerald-50'
                            : 'border-slate-200 bg-white hover:border-brand-400 hover:bg-brand-50/40 disabled:opacity-50',
                        )}
                      >
                        <p
                          className={cn(
                            'text-sm font-semibold',
                            isSelected ? 'text-emerald-800' : 'text-slate-800 group-hover:text-brand-900',
                          )}
                        >
                          {t.name}
                        </p>
                        <p className="mt-1 line-clamp-2 text-xs text-slate-500">{t.description}</p>
                        {isSelected ? (
                          <p className="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2 py-0.5 text-[11px] font-medium text-white">
                            ✓ Выбрано
                          </p>
                        ) : (
                          <p className="mt-2 flex items-center gap-1 text-[11px] font-medium text-brand-700 opacity-0 transition-opacity group-hover:opacity-100">
                            <CheckCircle2 className="h-3 w-3" />
                            Создать ТЗ (заполнение вручную)
                          </p>
                        )}
                      </button>
                    )
                  })}
                </div>
              </Card>
            </div>
          ) : (
            <TzBuilder requestId={requestId} tz={tz} request={request} />
          )}
        </div>

        <div className="flex w-full shrink-0 flex-col gap-3 xl:w-[400px]">
          <Tabs
            items={[
              { value: 'chat', label: <span className="flex items-center justify-center gap-1.5"><MessageSquare className="h-3.5 w-3.5" />Чат</span> },
              { value: 'analysis', label: <span className="flex items-center justify-center gap-1.5"><PieChart className="h-3.5 w-3.5" />Анализ</span> },
              { value: 'export', label: <span className="flex items-center justify-center gap-1.5"><FileCheck2 className="h-3.5 w-3.5" />Документы</span> },
            ]}
            value={tab}
            onChange={setTab}
          />
          <div className="min-h-[420px] flex-1 overflow-y-auto xl:h-auto xl:min-h-0">
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

      <Modal open={headerOpen} onClose={() => setHeaderOpen(false)} title="Редактирование заявки" className="max-w-2xl">
        <RequestHeaderForm
          request={request}
          onSaved={() => {
            invalidate()
            setHeaderOpen(false)
          }}
        />
      </Modal>
    </div>
  )
}
