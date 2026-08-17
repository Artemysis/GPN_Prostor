import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Building2, CheckCircle2, FileText, History, Package, Sparkles } from 'lucide-react'
import type { ChatAction, ChatMessage as ChatMessageType, Company, Contract, Product, TzTemplateSummary } from '@/lib/api'
import { api } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Stars } from '@/components/ui/misc'
import { cn } from '@/lib/utils'

const fieldLabels: Record<string, string> = {
  company_id: 'Подрядчик',
  contract_id: 'Договор',
  product_id: 'Продукт',
  cost_total: 'Стоимость, ₽',
  date_start: 'Начало',
  date_end: 'Окончание',
  title: 'Название',
}

function resolveValue(
  field: string | undefined,
  value: string | undefined,
  refs: { companies: Company[]; products: Product[]; contracts: Contract[] },
): string {
  if (!field || value === undefined) return value ?? ''
  if (field === 'company_id') return refs.companies.find((c) => c.company_id === value)?.name ?? value
  if (field === 'product_id') return refs.products.find((p) => p.product_id === value)?.product_name ?? value
  if (field === 'contract_id') return refs.contracts.find((k) => k.contract_id === value)?.contract_number ?? value
  if (field === 'cost_total') return Number(value).toLocaleString('ru-RU')
  return value
}

function ActionsPanel({
  actions,
  onApply,
  onCreateTz,
}: {
  actions: ChatAction[]
  onApply: (selected: ChatAction[]) => void
  onCreateTz: (templateId: string) => void
}) {
  const setFields = actions.filter((a) => a.type === 'set_field')
  const templateAction = actions.find((a) => a.type === 'suggest_template')
  const [selected, setSelected] = useState<Record<number, boolean>>(
    Object.fromEntries(setFields.map((a, i) => [i, !a.applied])),
  )
  const chosen = setFields.filter((_, i) => selected[i])
  const { data: companies = [] } = useQuery({ queryKey: ['companies'], queryFn: () => api.listCompanies(), staleTime: Infinity })
  const { data: products = [] } = useQuery({ queryKey: ['products'], queryFn: () => api.listProducts(), staleTime: Infinity })
  const { data: contracts = [] } = useQuery({ queryKey: ['contracts'], queryFn: () => api.listContracts(), staleTime: Infinity })
  const { data: templates = [] } = useQuery<TzTemplateSummary[]>({ queryKey: ['templates'], queryFn: () => api.listTemplates(), staleTime: Infinity })
  const template = templateAction ? templates.find((t) => t.id === templateAction.template_id) : undefined

  return (
    <div className="mt-3 space-y-2">
      {setFields.length > 0 && (
        <div className="rounded-xl border border-brand-100 bg-brand-50/60 p-3">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-800">
            <Sparkles className="h-3.5 w-3.5" />
            Предложения ИИ — подтвердите применение
          </p>
          <div className="space-y-1.5">
            {setFields.map((a, i) => (
              <label
                key={i}
                className={cn(
                  'flex cursor-pointer items-start gap-2.5 rounded-lg border bg-white px-3 py-2 text-sm transition-colors',
                  a.applied ? 'border-emerald-200 opacity-70' : selected[i] ? 'border-brand-300' : 'border-slate-200',
                )}
              >
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 accent-brand-800"
                  checked={a.applied ? true : Boolean(selected[i])}
                  disabled={a.applied}
                  onChange={(e) => setSelected((prev) => ({ ...prev, [i]: e.target.checked }))}
                />
                <span className="flex-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-700">{fieldLabels[a.field ?? ''] ?? a.field}</span>
                    <ArrowRight className="h-3 w-3 text-slate-400" />
                    <span className="font-semibold text-brand-800">{resolveValue(a.field, a.value, { companies, products, contracts })}</span>
                    {a.applied ? (
                      <Badge variant="success">
                        <CheckCircle2 className="h-3 w-3" />
                        применено
                      </Badge>
                    ) : (
                      <Badge variant="outline">уверенность {Math.round(a.confidence * 100)}%</Badge>
                    )}
                  </span>
                  {a.justification && <span className="mt-0.5 block text-xs text-slate-500">{a.justification}</span>}
                </span>
              </label>
            ))}
          </div>
          <div className="mt-2.5 flex items-center justify-between">
            <p className="text-[11px] text-brand-700/70">Ничего не применяется без вашего подтверждения</p>
            <Button size="sm" disabled={chosen.length === 0} onClick={() => onApply(chosen)}>
              Применить выбранные ({chosen.length})
            </Button>
          </div>
        </div>
      )}

      {templateAction && template && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-brand-200 bg-white px-3 py-2.5">
          <div className="flex items-start gap-2.5">
            <FileText className="mt-0.5 h-4 w-4 text-brand-700" />
            <div>
              <p className="text-sm font-medium text-slate-800">
                Рекомендация шаблона ТЗ: <span className="text-brand-800">{template.name}</span>
              </p>
              <p className="text-xs text-slate-500">
                Уверенность {Math.round(templateAction.confidence * 100)}% — создайте ТЗ, если согласны с рекомендацией
              </p>
            </div>
          </div>
          <TemplateCreateButton templateId={template.id} onCreateTz={onCreateTz} />
        </div>
      )}
    </div>
  )
}

function TemplateCreateButton({ templateId, onCreateTz }: { templateId: string; onCreateTz: (templateId: string) => void }) {
  const [used, setUsed] = useState(false)
  return (
    <Button
      size="sm"
      variant={used ? 'secondary' : 'default'}
      disabled={used}
      onClick={() => {
        onCreateTz(templateId)
        setUsed(true)
      }}
    >
      {used ? 'Создано' : 'Создать ТЗ'}
    </Button>
  )
}

export function ChatMessageView({
  message,
  streaming,
  onApply,
  onCreateTz,
}: {
  message: ChatMessageType
  streaming?: boolean
  onApply: (actions: ChatAction[]) => void
  onCreateTz: (templateId: string) => void
}) {
  const isUser = message.role === 'user'

  return (
    <div className={cn('flex gap-2.5', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold',
          isUser ? 'bg-slate-200 text-slate-600' : 'bg-brand-800 text-white',
        )}
      >
        {isUser ? 'ВЫ' : 'ИИ'}
      </div>
      <div className={cn('max-w-[85%] space-y-1', isUser && 'text-right')}>
        <div
          className={cn(
            'inline-block whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-left text-sm leading-relaxed',
            isUser ? 'rounded-tr-sm bg-brand-800 text-white' : 'rounded-tl-sm border border-slate-200 bg-white text-slate-700',
            streaming && 'chat-stream-cursor',
          )}
        >
          {message.content}
        </div>

        {!isUser && message.suggestions && (
          <div className="space-y-2 pt-1 text-left">
            {message.suggestions.products && message.suggestions.products.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-2.5">
                <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  <Package className="h-3.5 w-3.5" />
                  Продукты
                </p>
                <div className="space-y-1.5">
                  {message.suggestions.products.map((p) => (
                    <div key={p.product_id} className="flex items-start justify-between gap-2 rounded-lg bg-slate-50 px-2.5 py-2">
                      <div>
                        <p className="text-sm font-medium text-slate-800">{p.product_name}</p>
                        <p className="text-xs text-slate-500">{p.justification}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {message.suggestions.contractors && message.suggestions.contractors.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-2.5">
                <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  <Building2 className="h-3.5 w-3.5" />
                  Подрядчики
                </p>
                <div className="space-y-1.5">
                  {message.suggestions.contractors.map((c) => (
                    <div key={c.company_id} className="rounded-lg bg-slate-50 px-2.5 py-2">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-slate-800">{c.name}</p>
                        <Stars rating={c.rating} />
                      </div>
                      <p className="text-xs text-slate-500">{c.justification}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {message.suggestions.similar_requests && message.suggestions.similar_requests.length > 0 && (
              <div className="rounded-xl border border-slate-200 bg-white p-2.5">
                <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  <History className="h-3.5 w-3.5" />
                  Похожие заявки
                </p>
                <div className="space-y-1.5">
                  {message.suggestions.similar_requests.map((s) => (
                    <div key={s.request_id} className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-2.5 py-2">
                      <p className="truncate text-sm text-slate-700">{s.title}</p>
                      <Badge variant="outline">схожесть {Math.round(s.similarity * 100)}%</Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!isUser && message.actions && message.actions.length > 0 && !streaming && (
          <ActionsPanel actions={message.actions} onApply={onApply} onCreateTz={onCreateTz} />
        )}

        {streaming && <p className="text-[11px] text-slate-400">ИИ печатает…</p>}
      </div>
    </div>
  )
}
