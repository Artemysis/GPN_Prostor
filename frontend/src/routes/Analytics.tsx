import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BarChart3, FileStack, Search, Star, TriangleAlert } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Stars } from '@/components/ui/misc'
import { PageLoader } from '@/components/ui/misc'

const COLORS = ['#0E2E8F', '#2F63E5', '#5A87F0', '#8AADF7', '#B9CDFB', '#DCE7FD']

export default function Analytics() {
  const { data: tz, isLoading: loadingTz } = useQuery({ queryKey: ['analytics', 'tz'], queryFn: () => api.getAnalyticsTz() })
  const { data: search, isLoading: loadingSearch } = useQuery({ queryKey: ['analytics', 'search'], queryFn: () => api.getAnalyticsSearch() })

  if (loadingTz || loadingSearch || !tz || !search) return <PageLoader label="Загрузка аналитики…" />

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-6 py-8">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Аналитика</h1>
        <p className="mt-0.5 text-sm text-slate-500">Дашборды конструктора ТЗ и ИИ-поиска</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Всего ТЗ</p>
            <FileStack className="h-4 w-4 text-brand-700" />
          </div>
          <p className="mt-2 text-3xl font-bold text-slate-900">{tz.total_tz}</p>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Средняя готовность</p>
            <BarChart3 className="h-4 w-4 text-brand-700" />
          </div>
          <p className="mt-2 text-3xl font-bold text-slate-900">{tz.avg_completeness}%</p>
        </Card>
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Топ услуга</p>
            <Search className="h-4 w-4 text-brand-700" />
          </div>
          <p className="mt-2 truncate text-lg font-bold text-slate-900">{search.top_services[0]?.name ?? '—'}</p>
          <p className="text-xs text-slate-400">{search.top_services[0] ? `${search.top_services[0].count} заявок` : ''}</p>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>ТЗ по типам</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tz.by_type} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EEF2F7" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#64748B' }} allowDecimals={false} />
                <YAxis type="category" dataKey="type" width={190} tick={{ fontSize: 10, fill: '#475569' }} />
                <Tooltip cursor={{ fill: '#DCE7FD55' }} contentStyle={{ borderRadius: 12, border: '1px solid #E2E8F0', fontSize: 12 }} />
                <Bar dataKey="count" name="Кол-во ТЗ" radius={[0, 6, 6, 0]} barSize={18}>
                  {tz.by_type.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Популярные этапы работ</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tz.by_stage_popularity} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EEF2F7" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#64748B' }} allowDecimals={false} />
                <YAxis type="category" dataKey="stage" width={210} tick={{ fontSize: 10, fill: '#475569' }} />
                <Tooltip cursor={{ fill: '#DCE7FD55' }} contentStyle={{ borderRadius: 12, border: '1px solid #E2E8F0', fontSize: 12 }} />
                <Bar dataKey="count" name="Использований" radius={[0, 6, 6, 0]} barSize={14} fill="#2F63E5" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Топ подрядчиков</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {search.top_contractors.map((c) => (
              <div key={c.name} className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-800">{c.name}</p>
                  <Stars rating={c.rating} />
                </div>
                <span className="shrink-0 rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-bold text-brand-800">{c.count}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Типовые ошибки в ТЗ</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {tz.typical_errors.length === 0 && <p className="text-sm text-slate-400">Ошибок не найдено</p>}
            {tz.typical_errors.map((e) => (
              <div key={e.title} className="flex items-start gap-2">
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                <p className="flex-1 text-sm text-slate-700">{e.title}</p>
                <span className="shrink-0 text-xs font-bold text-amber-600">{e.count}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Незаполненные поля</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2.5">
            {search.unfilled_fields.map((f) => (
              <div key={f.field} className="flex items-center gap-2">
                <Star className="h-3.5 w-3.5 shrink-0 text-slate-300" />
                <p className="flex-1 text-sm text-slate-700">{f.field}</p>
                <span className="shrink-0 text-xs font-bold text-slate-500">{f.count}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
