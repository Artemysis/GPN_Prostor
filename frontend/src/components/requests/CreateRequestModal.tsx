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
  const queryClient = useQueryClient()
  const createdRef = useRef(false)

  useEffect(() => {
    if (open && !createdRef.current) {
      createdRef.current = true
      void api.createRequest({}).then((request) => {
        setRequestId(request.id)
        setHasTz(false)
        queryClient.invalidateQueries({ queryKey: ['requests'] })
      })
    }
    if (!open) {
      createdRef.current = false
      setRequestId(null)
      setHasTz(false)
    }
  }, [open, queryClient])

  const { data: request } = useQuery({
    queryKey: ['request', requestId],
    queryFn: () => api.getRequest(requestId as string),
    enabled: Boolean(requestId),
  })

  const invalidate = () => {
    if (requestId) queryClient.invalidateQueries({ queryKey: ['request', requestId] })
    queryClient.invalidateQueries({ queryKey: ['requests'] })
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
        <div className={cn(hasTz ? 'h-[calc(92vh-65px)]' : '')}>
          {!hasTz ? (
            <>
              <div className="mb-5 flex items-center gap-2 text-xs">
                <StepChip active>1. Шапка заявки</StepChip>
                <span className="h-px w-6 bg-slate-200" />
                <StepChip>2. Конструктор ТЗ</StepChip>
                <span className="h-px w-6 bg-slate-200" />
                <StepChip>3. Анализ и выгрузка</StepChip>
              </div>
              <div className="grid grid-cols-[minmax(0,1fr)_380px] gap-5">
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-card">
                  <RequestHeaderForm request={request} onSaved={invalidate} />
                </div>
                <AiChat
                  className="max-h-[560px]"
                  requestId={requestId}
                  onApplied={invalidate}
                  onCreateTz={(templateId) => {
                    void api.createTz(requestId, templateId, true).then(() => {
                      setHasTz(true)
                      invalidate()
                    })
                  }}
                />
              </div>
              <div className="mt-4 flex items-center gap-2 rounded-xl border border-brand-100 bg-brand-50/60 px-4 py-3 text-xs text-brand-900/80">
                <MessageSquare className="h-4 w-4 shrink-0" />
                Следующий шаг: выберите тип ТЗ вручную на карточках справа от чата или примените рекомендацию ИИ. Блоки ТЗ можно
                заполнять вручную и кнопкой «Заполнить ИИ» — каждый блок отдельно.
              </div>
            </>
          ) : (
            <RequestWorkspace requestId={requestId} />
          )}
        </div>
      )}
    </Modal>
  )
}

function StepChip({ active, children }: { active?: boolean; children: React.ReactNode }) {
  return (
    <span
      className={
        'rounded-full px-3 py-1 font-medium ' +
        (active ? 'bg-brand-800 text-white' : 'border border-slate-200 bg-white text-slate-400')
      }
    >
      {children}
    </span>
  )
}
