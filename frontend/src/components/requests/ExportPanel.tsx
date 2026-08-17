import { useEffect, useState } from 'react'
import { Download, FileDown, FileText, Paperclip, Sparkles, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import type { DocumentRecord } from '@/lib/api'
import { useJobPolling } from '@/lib/hooks/useJobPolling'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/controls'
import { useUiStore } from '@/lib/stores/uiStore'
import { formatBytes, formatDateTime } from '@/lib/utils'

const kindLabels: Record<string, string> = {
  tz_final: 'Итоговое ТЗ',
  analytical_report: 'Аналит. отчет ИИ',
  attachment: 'Приложение',
  kp: 'КП',
  rs: 'РС',
}

export function ExportPanel({ requestId }: { requestId: string }) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([])
  const [docx, setDocx] = useState(true)
  const [pdf, setPdf] = useState(false)
  const [includeReport, setIncludeReport] = useState(true)
  const [jobId, setJobId] = useState<string | null>(null)
  const toast = useUiStore((s) => s.toast)

  const refresh = () => setDocuments(api.listDocuments(requestId))
  useEffect(refresh, [requestId])

  useJobPolling(jobId, (job) => {
    if (job.status === 'done') {
      setJobId(null)
      refresh()
      toast('Документы сформированы', 'success')
    } else if (job.status === 'failed') {
      setJobId(null)
      toast('Ошибка формирования документов', 'error')
    }
  })

  const run = () => {
    const formats = [docx && 'docx', pdf && 'pdf'].filter(Boolean) as string[]
    if (formats.length === 0) {
      toast('Выберите хотя бы один формат', 'error')
      return
    }
    const job = api.startExport(requestId, formats, includeReport)
    setJobId(job.id)
  }

  const upload = async (file: File | undefined) => {
    if (!file) return
    await api.uploadAttachment(requestId, file)
    refresh()
    toast('Приложение загружено', 'success')
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
        <p className="mb-3 text-sm font-semibold text-slate-800">Формирование выгрузки</p>
        <div className="flex flex-wrap items-center gap-4">
          <Checkbox label="DOCX" checked={docx} onChange={(e) => setDocx(e.target.checked)} />
          <Checkbox label="PDF" checked={pdf} onChange={(e) => setPdf(e.target.checked)} />
          <Checkbox label="Аналитический отчет ИИ" checked={includeReport} onChange={(e) => setIncludeReport(e.target.checked)} />
          <Button className="ml-auto" size="sm" onClick={run} loading={Boolean(jobId)}>
            <FileDown className="h-3.5 w-3.5" />
            Выгрузить
          </Button>
        </div>
        <p className="mt-2 text-[11px] text-slate-400">
          В выгрузку входят итоговый документ ТЗ, приложения (КП, РС) и аналитический отчет, созданный ИИ
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <p className="text-sm font-semibold text-slate-800">Документы ({documents.length})</p>
          <label className="cursor-pointer">
            <input type="file" className="hidden" onChange={(e) => void upload(e.target.files?.[0])} />
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50">
              <Paperclip className="h-3.5 w-3.5" />
              Приложить файл
            </span>
          </label>
        </div>
        <div className="divide-y divide-slate-50">
          {documents.length === 0 && <p className="px-4 py-6 text-center text-sm text-slate-400">Документов пока нет</p>}
          {documents.map((d) => (
            <div key={d.id} className="flex items-center gap-3 px-4 py-2.5">
              <FileText className="h-4 w-4 shrink-0 text-brand-700" />
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 truncate text-sm font-medium text-slate-800">
                  {d.filename}
                  {d.generated_by_ai && (
                    <Badge variant="ai">
                      <Sparkles className="h-3 w-3" />
                      ИИ
                    </Badge>
                  )}
                </p>
                <p className="text-[11px] text-slate-400">
                  {kindLabels[d.kind] ?? d.kind} · {formatBytes(d.size_bytes)} · {formatDateTime(d.created_at)}
                </p>
              </div>
              {d.kind === 'attachment' && (
                <button
                  className="rounded-lg p-1.5 text-slate-300 hover:bg-red-50 hover:text-red-500"
                  onClick={() => {
                    api.deleteAttachment(d.id)
                    refresh()
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
              <Button size="sm" variant="outline" onClick={() => api.downloadDocument(d.id)}>
                <Download className="h-3.5 w-3.5" />
                Скачать
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
