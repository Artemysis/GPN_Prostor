import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Calendar, Check, ChevronDown, Plus, Sparkles, Trash2, X } from 'lucide-react'
import { api } from '@/lib/api'
import type { TzStage, TzTemplate } from '@/lib/api'
import { useJobPolling } from '@/lib/hooks/useJobPolling'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input, Label, Select, Textarea } from '@/components/ui/controls'
import { Progress } from '@/components/ui/misc'
import { FilledByBadge } from '@/components/shared/badges'
import { useUiStore } from '@/lib/stores/uiStore'

export function TzStageEditor({
  requestId,
  tz,
  template,
}: {
  requestId: string
  tz: TzStage[]
  template: TzTemplate
}) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [showSkeleton, setShowSkeleton] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [draft, setDraft] = useState<TzStage[] | null>(null)
  const queryClient = useQueryClient()
  const toast = useUiStore((s) => s.toast)

  useJobPolling(jobId, (job) => {
    if (job.status === 'done') {
      const result = job.result as { stages?: TzStage[] }
      setDraft(result.stages ?? [])
      setJobId(null)
    } else if (job.status === 'failed') {
      toast('ИИ не смог дополнить этапы', 'error')
      setJobId(null)
    }
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['tz', requestId] })
    queryClient.invalidateQueries({ queryKey: ['request', requestId] })
  }

  const patchStage = (id: string, patch: Partial<TzStage>) => {
    api.updateStage(requestId, id, patch)
    refresh()
  }

  const applyDraft = () => {
    if (!draft) return
    for (const st of draft) {
      api.addStage(requestId, { ...st, stage_order: st.stage_order })
    }
    setDraft(null)
    toast(`Добавлено этапов ИИ: ${draft.length}`, 'success')
    refresh()
  }

  const unusedSkeleton = template.stages.filter((s) => !tz.some((t) => t.stage_name === s.stage_name))
  const blockPct = tz.length === 0 ? 0 : Math.min(100, Math.round((tz.reduce((acc, s) => acc + (s.requirements ? 0.3 : 0) + (s.expected_results ? 0.3 : 0) + 0.4, 0) / tz.length) * 100))

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/60 px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-800 text-xs font-bold text-white">4</span>
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              Содержание работ
              <FilledByBadge value={tz.some((s) => s.filled_by === 'ai') ? (tz.every((s) => s.filled_by === 'ai') ? 'ai' : 'mixed') : 'manual'} />
            </p>
            <div className="mt-1 flex items-center gap-2">
              <Progress value={blockPct} className="w-24" />
              <span className="text-[11px] font-medium text-slate-500">{blockPct}% · этапов: {tz.length}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="secondary" loading={Boolean(jobId)} onClick={() => { setDraft(null); const job = api.startFillAi(requestId, 'work_content'); setJobId(job.id) }}>
            <Sparkles className="h-3.5 w-3.5" />
            Дополнить ИИ
          </Button>
          <div className="relative">
            <Button size="sm" onClick={() => setShowSkeleton((v) => !v)}>
              <Plus className="h-3.5 w-3.5" />
              Добавить этап
            </Button>
            {showSkeleton && (
              <div className="absolute right-0 top-full z-10 mt-1 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-card">
                {unusedSkeleton.length === 0 && <p className="px-2 py-1.5 text-xs text-slate-400">Все типовые этапы уже добавлены</p>}
                {unusedSkeleton.map((s) => (
                  <button
                    key={s.stage_order}
                    className="block w-full rounded-lg px-2 py-2 text-left text-xs text-slate-700 hover:bg-brand-50"
                    onClick={() => {
                      api.addStage(requestId, { stage_name: s.stage_name, requirements: '', expected_results: '' })
                      setShowSkeleton(false)
                      refresh()
                    }}
                  >
                    <span className="font-semibold text-brand-800">Типовой:</span> {s.stage_name}
                  </button>
                ))}
                <button
                  className="mt-1 block w-full rounded-lg border-t border-slate-100 px-2 py-2 text-left text-xs text-slate-600 hover:bg-slate-50"
                  onClick={() => {
                    const st = api.addStage(requestId, { stage_name: `Этап ${tz.length + 1}` })
                    setOpenId(st.id)
                    setShowSkeleton(false)
                    refresh()
                  }}
                >
                  Пустой этап
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-3 px-5 py-4">
        {draft && (
          <div className="rounded-xl border-2 border-dashed border-brand-300 bg-brand-50/70 p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-800">
                <Sparkles className="h-3.5 w-3.5" />
                Черновик этапов от ИИ ({draft.length})
              </p>
              <div className="flex gap-2">
                <Button size="sm" onClick={applyDraft}>
                  <Check className="h-3.5 w-3.5" />
                  Добавить все
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                  <X className="h-3.5 w-3.5" />
                  Отклонить
                </Button>
              </div>
            </div>
            <div className="space-y-1.5">
              {draft.map((s) => (
                <div key={s.id} className="rounded-lg bg-white px-3 py-2 text-sm">
                  <p className="font-medium text-brand-900">{s.stage_name}</p>
                  <p className="text-xs text-slate-500">Требования: {s.requirements || '—'}</p>
                  <p className="text-xs text-slate-500">Результаты: {s.expected_results || '—'}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {tz.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 px-4 py-8 text-center">
            <p className="text-sm text-slate-500">Этапы не заданы</p>
            <p className="mt-1 text-xs text-slate-400">Добавьте типовые этапы шаблона, создайте пустые или попросите ИИ дополнить</p>
          </div>
        )}

        {tz.map((s) => (
          <div key={s.id} className="rounded-xl border border-slate-200">
            <div className="flex items-center justify-between gap-3 px-4 py-3">
              <button className="flex min-w-0 flex-1 items-center gap-3 text-left" onClick={() => setOpenId(openId === s.id ? null : s.id)}>
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-brand-50 text-xs font-bold text-brand-800">
                  {s.stage_order}
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-slate-800">{s.stage_name || 'Без названия'}</span>
                    <FilledByBadge value={s.filled_by} />
                  </span>
                  <span className="block truncate text-xs text-slate-400">
                    {s.requirements ? `Требования: ${s.requirements}` : 'требования не указаны'}
                  </span>
                </span>
              </button>
              <div className="flex shrink-0 items-center gap-1">
                <button
                  className="rounded-lg p-1.5 text-slate-300 hover:bg-red-50 hover:text-red-500"
                  onClick={() => {
                    api.deleteStage(requestId, s.id)
                    refresh()
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
                <ChevronDown className={'h-4 w-4 text-slate-400 transition-transform ' + (openId === s.id ? 'rotate-180' : '')} />
              </div>
            </div>

            {openId === s.id && (
              <div className="grid grid-cols-2 gap-3 border-t border-slate-100 px-4 py-3">
                <div className="col-span-2">
                  <Label>Наименование этапа</Label>
                  <Input value={s.stage_name} onChange={(e) => patchStage(s.id, { stage_name: e.target.value })} />
                </div>
                <div>
                  <Label>Требования к выполнению</Label>
                  <Textarea rows={3} value={s.requirements} placeholder={template.stages.find((x) => x.stage_name === s.stage_name)?.default_requirements} onChange={(e) => patchStage(s.id, { requirements: e.target.value })} />
                </div>
                <div>
                  <Label>Ожидаемые результаты</Label>
                  <Textarea rows={3} value={s.expected_results} placeholder={template.stages.find((x) => x.stage_name === s.stage_name)?.default_results} onChange={(e) => patchStage(s.id, { expected_results: e.target.value })} />
                </div>
                <div className="col-span-2">
                  <Label>Описание работы</Label>
                  <Textarea rows={2} value={s.description} onChange={(e) => patchStage(s.id, { description: e.target.value })} />
                </div>
                <div className="col-span-2 grid grid-cols-2 gap-3">
                  <div>
                    <Label>
                      <Calendar className="mr-1 inline h-3 w-3" />
                      Начало этапа
                    </Label>
                    <Input type="date" value={s.stage_start_date ?? ''} onChange={(e) => patchStage(s.id, { stage_start_date: e.target.value || null })} />
                  </div>
                  <div>
                    <Label>Окончание этапа</Label>
                    <Input type="date" value={s.stage_end_date ?? ''} onChange={(e) => patchStage(s.id, { stage_end_date: e.target.value || null })} />
                  </div>
                </div>
                <div className="col-span-2">
                  <Label>Заполнено</Label>
                  <Select value={s.filled_by} onChange={(e) => patchStage(s.id, { filled_by: e.target.value as TzStage['filled_by'] })}>
                    <option value="manual">Вручную</option>
                    <option value="ai">ИИ</option>
                    <option value="mixed">Смешанно</option>
                  </Select>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}
