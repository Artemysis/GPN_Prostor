import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, BarChart3, CheckCircle2, Lightbulb, ScanSearch } from 'lucide-react'
import { api } from '@/lib/api'
import type { TzAnalysis } from '@/lib/api'
import { useJobPolling } from '@/lib/hooks/useJobPolling'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/misc'
import { useUiStore } from '@/lib/stores/uiStore'
import { formatDateTime } from '@/lib/utils'

const severityStyles: Record<string, { badge: 'danger' | 'warning' | 'slate'; label: string }> = {
  high: { badge: 'danger', label: 'Высокий' },
  medium: { badge: 'warning', label: 'Средний' },
  low: { badge: 'slate', label: 'Низкий' },
}

export function TzAnalysisPanel({ requestId, onAskAi }: { requestId: string; onAskAi: (question: string) => void }) {
  const [analysis, setAnalysis] = useState<TzAnalysis | null>(() => api.getAnalysis(requestId))
  const [jobId, setJobId] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const toast = useUiStore((s) => s.toast)

  useJobPolling(jobId, (job) => {
    if (job.status === 'done') {
      setAnalysis(job.result as TzAnalysis)
      setJobId(null)
      queryClient.invalidateQueries({ queryKey: ['request', requestId] })
    } else if (job.status === 'failed') {
      toast('Анализ завершился ошибкой', 'error')
      setJobId(null)
    }
  })

  const run = () => {
    const job = api.startAnalyze(requestId)
    setJobId(job.id)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-400">
          {analysis ? `Последний анализ: ${formatDateTime(analysis.analyzed_at)}` : 'Анализ еще не проводился'}
        </p>
        <Button size="sm" onClick={run} loading={Boolean(jobId)}>
          <ScanSearch className="h-3.5 w-3.5" />
          Анализировать
        </Button>
      </div>

      {!analysis && !jobId && (
        <div className="rounded-xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-400">
          Запустите анализ — система проверит полноту, риски и даст рекомендации
        </div>
      )}

      {analysis && (
        <>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
            <div className="mb-3 flex items-center gap-4">
              <div className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded-2xl bg-brand-800 text-white">
                <span className="text-xl font-bold leading-none">{analysis.completeness_pct}</span>
                <span className="text-[10px] opacity-80">готовность</span>
              </div>
              <div className="min-w-0 flex-1 space-y-1.5">
                {Object.entries(analysis.block_completeness).map(([code, pct]) => (
                  <div key={code} className="flex items-center gap-2">
                    <span className="w-32 shrink-0 truncate text-xs text-slate-500">{code}</span>
                    <Progress value={pct} className="flex-1" />
                    <span className="w-9 shrink-0 text-right text-xs font-medium text-slate-600">{pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <AlertTriangle className="h-3.5 w-3.5" />
              Риски ({analysis.risks.length})
            </p>
            <div className="space-y-2">
              {analysis.risks.length === 0 && (
                <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-sm text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" />
                  Риски не выявлены
                </div>
              )}
              {analysis.risks.map((r, i) => (
                <div key={i} className="rounded-xl border border-slate-200 bg-white p-3 shadow-card">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={severityStyles[r.severity].badge}>{severityStyles[r.severity].label}</Badge>
                    <Badge variant="outline">{r.category}</Badge>
                    <Badge variant="slate">блок: {r.block_code}</Badge>
                    <span className="text-sm font-semibold text-slate-800">{r.title}</span>
                  </div>
                  <p className="mt-1.5 text-xs text-slate-500">{r.description}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-brand-800">
                      <BarChart3 className="mr-1 inline h-3 w-3" />
                      {r.suggestion}
                    </p>
                    <Button size="sm" variant="ghost" onClick={() => onAskAi(`Объясни риск «${r.title}» и предложи, как его устранить`)}>
                      Объяснить в чате
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              <Lightbulb className="h-3.5 w-3.5" />
              Рекомендации ({analysis.recommendations.length})
            </p>
            <div className="space-y-2">
              {analysis.recommendations.map((r, i) => (
                <div key={i} className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-card">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-brand-50 text-xs font-bold text-brand-800">
                    {r.priority}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-slate-800">{r.title}</p>
                    <p className="text-xs text-slate-500">{r.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
