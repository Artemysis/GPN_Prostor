import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Progress } from '@/components/ui/misc'
import { StatusBadge } from '@/components/shared/badges'
import { CreateRequestModal } from '@/components/requests/CreateRequestModal'
import { useUiStore } from '@/lib/stores/uiStore'
import { formatDate, formatMoney } from '@/lib/utils'

const filters: { value: string; label: string }[] = [
  { value: '', label: 'Все' },
  { value: 'draft', label: 'Черновики' },
  { value: 'submitted', label: 'Отправлены' },
  { value: 'deleted', label: 'Удалено' },
]

export default function RequestsList() {
  const [status, setStatus] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useUiStore((s) => s.toast)

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ['requests', status],
    queryFn: () => api.listRequests(status || undefined),
  })
  const { data: counts = {} } = useQuery({
    queryKey: ['requestCounts'],
    queryFn: async () => {
      const entries = await Promise.all(
        filters.filter((f) => f.value).map(async (f) => [f.value, (await api.listRequests(f.value)).length] as const),
      )
      return Object.fromEntries(entries) as Record<string, number>
    },
  })
  const { data: companies = [] } = useQuery({ queryKey: ['companies'], queryFn: () => api.listCompanies(), staleTime: Infinity })
  const { data: products = [] } = useQuery({ queryKey: ['products'], queryFn: () => api.listProducts(), staleTime: Infinity })

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requests'] })
      queryClient.invalidateQueries({ queryKey: ['requestCounts'] })
      toast('Заявка удалена', 'success')
    },
  })

  const filtered = requests

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 xl:py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Заявки</h1>
          <p className="mt-0.5 text-sm text-slate-500">Регистрация заявок на нефтесервисные работы</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4" />
          Создать заявку
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatus(f.value)}
            className={
              'rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ' +
              (status === f.value
                ? 'bg-brand-800 text-white shadow-sm'
                : 'border border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:text-brand-800')
            }
          >
            {f.label}
            {f.value && <span className="ml-1.5 text-xs opacity-70">{counts[f.value] ?? 0}</span>}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-brand-50/50 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2.5 font-semibold">Номер</th>
                <th className="w-full px-3 py-2.5 font-semibold">Название</th>
                <th className="hidden px-3 py-2.5 font-semibold md:table-cell">Исполнитель / продукт</th>
                <th className="hidden px-3 py-2.5 font-semibold lg:table-cell">Стоимость</th>
                <th className="hidden px-3 py-2.5 font-semibold lg:table-cell">Сроки</th>
                <th className="hidden px-3 py-2.5 font-semibold lg:table-cell">Готовность ТЗ</th>
                <th className="px-3 py-2.5 font-semibold">Статус</th>
                <th className="px-2 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-400">
                    Загрузка…
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-400">
                    Заявок пока нет
                  </td>
                </tr>
              ) : (
                filtered.map((r) => (
                  <tr
                    key={r.id}
                    className="cursor-pointer border-b border-slate-50 transition-colors last:border-0 hover:bg-brand-50/40"
                    onClick={() => navigate(`/requests/${r.id}`)}
                  >
                    <td className="whitespace-nowrap px-3 py-3 font-mono text-xs font-semibold text-brand-800">{r.number}</td>
                    <td className="px-3 py-3">
                      <p className="truncate font-medium text-slate-800">{r.title}</p>
                      <p className="text-xs text-slate-400">создана {formatDate(r.created_at)}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-500 md:hidden">
                        {companies.find((c) => c.company_id === r.company_id)?.name ?? '—'}
                      </p>
                    </td>
                    <td className="hidden max-w-[200px] px-3 py-3 text-xs text-slate-600 md:table-cell">
                      <p className="truncate">{companies.find((c) => c.company_id === r.company_id)?.name ?? '—'}</p>
                      <p className="truncate text-slate-400">
                        {products.find((p) => p.product_id === r.product_id)?.product_name ?? 'продукт не выбран'}
                      </p>
                    </td>
                    <td className="hidden whitespace-nowrap px-3 py-3 text-slate-700 lg:table-cell">
                      {formatMoney(r.cost_total, r.currency)}
                    </td>
                    <td className="hidden whitespace-nowrap px-3 py-3 text-xs text-slate-600 lg:table-cell">
                      {formatDate(r.date_start)} — {formatDate(r.date_end)}
                    </td>
                    <td className="hidden whitespace-nowrap px-3 py-3 lg:table-cell">
                      <TzCompletenessCell requestId={r.id} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-3">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-2 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          remove.mutate(r.id)
                        }}
                        className="rounded-lg p-1.5 text-slate-300 transition-colors hover:bg-red-50 hover:text-red-500"
                        title="Удалить"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {filtered.length === 0 && !isLoading && (
        <div className="mt-6 flex flex-col items-center gap-2 py-8 text-center text-slate-400">
          <FileText className="h-8 w-8" />
          <p className="text-sm">Создайте первую заявку — ИИ-консультант поможет заполнить шапку и подобрать шаблон ТЗ</p>
        </div>
      )}

      <CreateRequestModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}

function TzCompletenessCell({ requestId }: { requestId: string }) {
  const { data: tz } = useQuery({ queryKey: ['tz', requestId], queryFn: () => api.getTz(requestId) })
  if (!tz) return <span className="text-xs text-slate-400">нет ТЗ</span>
  return (
    <div className="flex items-center gap-2">
      <Progress value={tz.completeness_pct} className="w-10" />
      <span className="text-xs font-medium text-slate-600">{tz.completeness_pct}%</span>
    </div>
  )
}
