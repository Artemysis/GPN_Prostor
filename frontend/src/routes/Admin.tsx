import { useRef, useState } from 'react'
import { Database, RefreshCcw, Upload } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useJobPolling } from '@/lib/hooks/useJobPolling'
import { useUiStore } from '@/lib/stores/uiStore'

const ingestItems: { key: string; file: string; label: string; run: (file: File) => Promise<{ inserted: number; updated: number }> }[] = [
  { key: 'companies', file: '0. Компании.xlsx', label: 'Компании', run: api.ingestCompanies },
  { key: 'contracts', file: '1. Договоры.xlsx', label: 'Договоры', run: api.ingestContracts },
  { key: 'calculations', file: '2. Договор + РС.xlsx', label: 'Договор + РС', run: api.ingestCalculations },
  { key: 'products-rates', file: '3. Договор + продукты.xlsx', label: 'Продукты и расценки', run: (file) => api.ingestProductsRates(file) },
  { key: 'operations', file: '5. Продукты + Операции.xlsx', label: 'Операции продуктов', run: api.ingestOperations },
]

export default function Admin() {
  const [results, setResults] = useState<Record<string, { inserted: number; updated: number } | 'loading'>>({})
  const [embeddingJobId, setEmbeddingJobId] = useState<string | null>(null)
  const toast = useUiStore((s) => s.toast)
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({})

  useJobPolling(embeddingJobId, (job) => {
    if (job.status === 'done') {
      setEmbeddingJobId(null)
      toast('Индекс эмбеддингов пересобран', 'success')
    } else if (job.status === 'failed') {
      setEmbeddingJobId(null)
      toast('Ошибка пересборки индекса', 'error')
    }
  })

  const ingest = async (item: (typeof ingestItems)[number], file: File | undefined) => {
    if (!file) return
    setResults((prev) => ({ ...prev, [item.key]: 'loading' }))
    try {
      const result = await item.run(file)
      setResults((prev) => ({ ...prev, [item.key]: result }))
      toast(`Ингест «${file.name}» завершен`, 'success')
    } catch (error) {
      setResults((prev) => {
        const next = { ...prev }
        delete next[item.key]
        return next
      })
      toast(error instanceof Error ? error.message : 'Ошибка ингеста', 'error')
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4 px-6 py-8">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Администрирование</h1>
        <p className="mt-0.5 text-sm text-slate-500">Загрузка справочников из выгрузок ПРОСТОР и обслуживание индекса</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-4 w-4 text-brand-700" />
            Ингест xlsx-выгрузок
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {ingestItems.map((item) => {
            const result = results[item.key]
            return (
              <div key={item.key} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-800">{item.label}</p>
                  <p className="text-xs text-slate-400">{item.file}</p>
                </div>
                <div className="flex items-center gap-3">
                  {result === 'loading' && <span className="text-xs text-slate-400">Загрузка…</span>}
                  {result && result !== 'loading' && (
                    <span className="rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                      добавлено {result.inserted}, обновлено {result.updated}
                    </span>
                  )}
                  <input
                    ref={(el) => {
                      fileRefs.current[item.key] = el
                    }}
                    type="file"
                    accept=".xlsx"
                    className="hidden"
                    onChange={(e) => void ingest(item, e.target.files?.[0])}
                  />
                  <Button size="sm" variant="outline" onClick={() => fileRefs.current[item.key]?.click()}>
                    <Upload className="h-3.5 w-3.5" />
                    Загрузить
                  </Button>
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Векторный индекс (pgvector)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-slate-600">
              Пересборка эмбеддингов продуктов, услуг компаний, шаблонов ТЗ и заявок. Выполняется после ингеста.
            </p>
            <Button
              variant="outline"
              loading={Boolean(embeddingJobId)}
              onClick={() => {
                void api.rebuildEmbeddings().then((job) => setEmbeddingJobId(job.id))
              }}
            >
              <RefreshCcw className="h-4 w-4" />
              Пересобрать
            </Button>
          </div>
        </CardContent>
      </Card>

    </div>
  )
}
