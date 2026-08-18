import { useEffect, useRef, useState } from 'react'
import { FileText, MessageSquare } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Modal } from '@/components/ui/modal'
import { RequestHeaderForm } from './RequestHeaderForm'
import { AiChat } from './AiChat'
import { RequestWorkspace } from './RequestWorkspace'
import { cn } from '@/lib/utils'

export function CreateRequestModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [requestId, setRequestId] = useState<string | null>(null)
  const [hasTz, setHasTz] = useState(false)
  const [creatingTz, setCreatingTz] = useState(false)
  const [creatingWithAi, setCreatingWithAi] = useState(false)
  const [recommendedTemplateId, setRecommendedTemplateId] = useState<string | null>(null)
  const [chosenTemplateId, setChosenTemplateId] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const createdRef = useRef(false)

  useEffect(() => {
    if (open && !createdRef.current) {
      createdRef.current = true
      void api.createRequest({}).then((request) => {
        setRequestId(request.id)
        setHasTz(false)
        setRecommendedTemplateId(null)
        queryClient.invalidateQueries({ queryKey: ['requests'] })
      })
    }
    if (!open) {
      createdRef.current = false
      setRequestId(null)
      setHasTz(false)
      setRecommendedTemplateId(null)
      setChosenTemplateId(null)
    }
  }, [open, queryClient])

  const { data: request } = useQuery({
    queryKey: ['request', requestId],
    queryFn: () => api.getRequest(requestId as string),
    enabled: Boolean(requestId),
  })

  const { data: templates = [] } = useQuery({
    queryKey: ['templates'],
    queryFn: () => api.listTemplates(),
    enabled: Boolean(requestId) && !hasTz,
  })

  // ТЗ мог быть создан ранее (возврат с шага 2 или применение ИИ) — даём вернуться к нему
  const { data: existingTz } = useQuery({
    queryKey: ['tz', requestId],
    queryFn: () => api.getTz(requestId as string),
    enabled: Boolean(requestId) && !hasTz,
  })

  // Выбранный тип: клик по карточке или созданное ТЗ (закрепляется цветом)
  const selectedTemplateId = chosenTemplateId ?? existingTz?.template_id ?? null

  const invalidate = () => {
    if (requestId) queryClient.invalidateQueries({ queryKey: ['request', requestId] })
    queryClient.invalidateQueries({ queryKey: ['requests'] })
  }

  const createTz = (templateId: string, prefill = false) => {
    if (!requestId || creatingTz) return
    if (existingTz) {
      setHasTz(true) // ТЗ уже существует — просто возвращаемся к конструктору
      return
    }
    setChosenTemplateId(templateId) // сразу закрепляем выбор цветом
    setCreatingTz(true)
    setCreatingWithAi(prefill)
    void api
      .createTz(requestId, templateId, prefill)
      .then(() => {
        setHasTz(true)
        invalidate()
      })
      .finally(() => {
        setCreatingTz(false)
        setCreatingWithAi(false)
      })
  }

  const handleApplied = (result: { tz_diff?: { tz_id?: string } } | null) => {
    invalidate()
    if (result?.tz_diff?.tz_id) setHasTz(true)
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      className={cn('transition-all', hasTz ? 'max-w-[1400px]' : 'max-w-[1100px]')}
      bodyClassName={hasTz ? 'p-0' : 'p-6'}
      title={
        <span className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-brand-700" />
          Новая заявка {request ? `· ${request.number}` : ''}
        </span>
      }
      description={
        hasTz
          ? undefined
          : 'Заполните шапку вручную или обсудите задачу с ИИ-консультантом — он предложит варианты, а решение останется за вами'
      }
    >
      {requestId && request && (
        <div className={cn(hasTz ? 'xl:h-[calc(92vh-65px)]' : '')}>
          {!hasTz ? (
            <>
              <div className="mb-5 flex flex-wrap items-center gap-2 text-xs">
                <StepChip active>1. Шапка заявки</StepChip>
                <span className="h-px w-6 bg-slate-200" />
                <StepChip>2. Конструктор ТЗ</StepChip>
                <span className="h-px w-6 bg-slate-200" />
                <StepChip>3. Анализ и выгрузка</StepChip>
                {existingTz && (
                  <button
                    onClick={() => setHasTz(true)}
                    className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-brand-800 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-colors hover:bg-brand-900"
                  >
                    Продолжить работу с ТЗ →
                  </button>
                )}
              </div>
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-card">
                  <RequestHeaderForm request={request} onSaved={invalidate} />
                </div>
                <div className="flex min-h-0 flex-col gap-3">
                  <AiChat
                    className="h-[420px] min-h-0 flex-1 lg:h-auto"
                    requestId={requestId}
                    onApplied={handleApplied}
                    onTemplateRecommended={setRecommendedTemplateId}
                  />
                  <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-card">
                    <p className="text-xs font-semibold text-slate-800">Выберите тип ТЗ</p>
                    <p className="mt-0.5 text-[11px] text-slate-400">
                      Карточки ниже создадут пустой конструктор для ручного заполнения; ТЗ с ИИ-черновиком — через кнопку
                      «Применить и создать ТЗ» в предложениях ИИ-консультанта
                    </p>
                    {creatingTz && (
                      <div className="mt-2.5 space-y-1.5 rounded-lg bg-brand-50/60 px-3 py-2">
                        <p className="text-[11px] font-medium text-brand-800">
                          {creatingWithAi ? 'Создаём ТЗ с ИИ-предзаполнением…' : 'Создаём ТЗ…'}
                        </p>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
                          <div className="h-full w-1/3 animate-[progress-slide_1.4s_ease-in-out_infinite] rounded-full bg-brand-600" />
                        </div>
                      </div>
                    )}
                    <div className="mt-2.5 max-h-56 space-y-1.5 overflow-y-auto pr-0.5">
                      {templates.map((t) => {
                        const isSelected = t.id === selectedTemplateId
                        const isRecommended = t.id === recommendedTemplateId
                        const stateCls = isSelected
                          ? 'border-emerald-400 bg-emerald-50'
                          : isRecommended
                            ? 'border-brand-400 bg-brand-50/50 hover:bg-brand-50'
                            : 'border-slate-200 bg-white hover:border-brand-400 hover:bg-brand-50/40 disabled:opacity-50'
                        return (
                          <button
                            key={t.id}
                            onClick={() => createTz(t.id)}
                            disabled={creatingTz || isSelected}
                            className={cn(
                              'flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors',
                              stateCls,
                            )}
                          >
                            <span className={cn('font-semibold', isSelected ? 'text-emerald-800' : 'text-slate-800')}>
                              {t.name}
                            </span>
                            <span className="flex shrink-0 items-center gap-1.5">
                              {isRecommended && (
                                <span className="inline-flex items-center rounded-full bg-brand-800 px-2 py-0.5 text-[10px] font-medium text-white">
                                  Рекомендует ИИ
                                </span>
                              )}
                              {isSelected && (
                                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-medium text-white">
                                  ✓ Выбрано
                                </span>
                              )}
                            </span>
                          </button>
                        )
                      })}
                      {templates.length === 0 && (
                        <p className="px-1 py-2 text-[11px] text-slate-400">Список шаблонов загружается…</p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2 rounded-xl border border-brand-100 bg-brand-50/60 px-4 py-3 text-xs text-brand-900/80">
                <MessageSquare className="h-4 w-4 shrink-0" />
                Следующий шаг: выберите тип ТЗ вручную на карточках справа от чата или примените рекомендацию ИИ. Блоки ТЗ можно
                заполнять вручную и кнопкой «Заполнить ИИ» — каждый блок отдельно.
              </div>
            </>
          ) : (
            <div className="flex h-full min-h-0 flex-col">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-2">
                <div className="flex items-center gap-2 text-xs">
                  <StepChip onClick={() => setHasTz(false)}>1. Шапка заявки</StepChip>
                  <span className="h-px w-6 bg-slate-200" />
                  <StepChip active>2. Конструктор ТЗ</StepChip>
                  <span className="h-px w-6 bg-slate-200" />
                  <StepChip>3. Анализ и выгрузка</StepChip>
                </div>
                <button
                  onClick={() => setHasTz(false)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:border-brand-400 hover:text-brand-800"
                >
                  ← Изменить шапку заявки
                </button>
              </div>
              <div className="min-h-0 flex-1">
                <RequestWorkspace requestId={requestId} />
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

function StepChip({ active, children, onClick }: { active?: boolean; children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={
        'rounded-full px-3 py-1 font-medium transition-colors ' +
        (active ? 'bg-brand-800 text-white' : 'border border-slate-200 bg-white ' + (onClick ? 'cursor-pointer text-slate-600 hover:border-brand-400 hover:text-brand-800' : 'text-slate-400'))
      }
    >
      {children}
    </button>
  )
}
