import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { RequestRecord, RequestStatus } from '@/lib/api'
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
  { value: 'in_progress', label: 'В работе' },
  { value: 'ready', label: 'Готовы' },
  { value: 'submitted', label: 'Отправлены' },
]

export default function RequestsList() {
  const [status, setStatus] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useUiStore((s) => s.toast)

  const { data: requests = [], isLoading } = useQuery({
    queryKey: ['requests'],
    queryFn: () => api.listRequests(),
  })

  const remove = useMutation({
    mutationFn: async (id: string) => {
      api.deleteRequest(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requests'] })
      toast('Заявка удалена', 'success')
    },
  })

  const filtered = status ? requests.filter((r) => r.status === status) : requests

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
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
            {f.value && (
              <span className="ml-1.5 text-xs opacity-70">
                {requests.filter((r: RequestRecord) => r.status === (f.value as RequestStatus)).length}
              </span>
            )}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 bg-brand-50/50 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3 font-semibold">Номер</th>
              <th className="px-4 py-3 font-semibold">Название</th>
              <th className="px-4 py-3 font-semibold">Подрядчик / продукт</th>
              <th className="px-4 py-3 font-semibold">Стоимость</th>
              <th className="px-4 py-3 font-semibold">Сроки</th>
              <th className="px-4 py-3 font-semibold">Готовность ТЗ</th>
              <th className="px-4 py-3 font-semibold">Статус</th>
              <th className="px-4 py-3" />
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
              filtered.map((r) => {
                const tz = api.getTz(r.id)
                return (
                  <tr
                    key={r.id}
                    className="cursor-pointer border-b border-slate-50 transition-colors last:border-0 hover:bg-brand-50/40"
                    onClick={() => navigate(`/requests/${r.id}`)}
                  >
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-brand-800">{r.number}</td>
                    <td className="max-w-[280px] px-4 py-3">
                      <p className="truncate font-medium text-slate-800">{r.title}</p>
                      <p className="text-xs text-slate-400">создана {formatDate(r.created_at)}</p>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600">
                      <p className="truncate">{api.listCompanies().find((c) => c.company_id === r.company_id)?.name ?? '—'}</p>
                      <p className="truncate text-slate-400">
                        {api.listProducts().find((p) => p.product_id === r.product_id)?.product_name ?? 'продукт не выбран'}
                      </p>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-slate-700">{formatMoney(r.cost_total, r.currency)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                      {formatDate(r.date_start)} — {formatDate(r.date_end)}
                    </td>
                    <td className="px-4 py-3">
                      {tz ? (
                        <div className="flex items-center gap-2">
                          <Progress value={tz.completeness_pct} className="w-20" />
                          <span className="text-xs font-medium text-slate-600">{tz.completeness_pct}%</span>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400">нет ТЗ</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-4 py-3 text-right">
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
                )
              })
            )}
          </tbody>
        </table>
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
