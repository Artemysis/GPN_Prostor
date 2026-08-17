import { useEffect, useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Check, Save, Sparkles, X } from 'lucide-react'
import { api } from '@/lib/api'
import type { TzBlock, TzTemplateBlockSchema } from '@/lib/api'
import { useJobPolling } from '@/lib/hooks/useJobPolling'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input, Label, ListInput, Textarea } from '@/components/ui/controls'
import { Progress } from '@/components/ui/misc'
import { FilledByBadge } from '@/components/shared/badges'
import { useUiStore } from '@/lib/stores/uiStore'
import { isFilled } from '@/lib/api/drafts'

interface Draft {
  block_code: string
  content?: Record<string, unknown>
}

export function TzBlockCard({
  block,
  schema,
  requestId,
}: {
  block: TzBlock
  schema: TzTemplateBlockSchema
  requestId: string
}) {
  const [content, setContent] = useState<Record<string, unknown>>(block.content)
  const [baseline, setBaseline] = useState<Record<string, unknown>>(block.content)
  const [baselineFilledBy, setBaselineFilledBy] = useState(block.filled_by)
  const [jobId, setJobId] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const queryClient = useQueryClient()
  const toast = useUiStore((s) => s.toast)

  useEffect(() => {
    setContent(block.content)
    setBaseline(block.content)
    setBaselineFilledBy(block.filled_by)
    setDraft(null)
  }, [block])

  const dirty = useMemo(() => JSON.stringify(content) !== JSON.stringify(baseline), [content, baseline])

  useJobPolling(jobId, (job) => {
    if (job.status === 'done' && job.result) {
      setDraft(job.result as Draft)
      setJobId(null)
    } else if (job.status === 'failed') {
      toast('ИИ не смог заполнить блок', 'error')
      setJobId(null)
    }
  })

  const save = (next: Record<string, unknown>, filledBy: 'manual' | 'ai') => {
    void api.saveBlock(requestId, block.block_code, next, filledBy).then(() => {
      setBaseline(next)
      setBaselineFilledBy(filledBy === 'ai' ? 'ai' : baselineFilledBy === 'ai' ? 'mixed' : 'manual')
      setContent(next)
      queryClient.invalidateQueries({ queryKey: ['tz', requestId] })
      queryClient.invalidateQueries({ queryKey: ['request', requestId] })
      toast(`Блок «${block.block_name}» сохранен`, 'success')
    })
  }

  const fillAi = () => {
    setDraft(null)
    void api.startFillAi(requestId, block.block_code).then((job) => setJobId(job.id))
  }

  const field = (key: string) => content[key]
  const setField = (key: string, value: unknown) => setContent((prev) => ({ ...prev, [key]: value }))
  const draftField = (key: string) => draft?.content?.[key]

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/60 px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-800 text-xs font-bold text-white">
            {schema.order}
          </span>
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              {block.block_name}
              <FilledByBadge value={baselineFilledBy} />
            </p>
            <div className="mt-1 flex items-center gap-2">
              <Progress value={block.completeness_pct} className="w-24" />
              <span className="text-[11px] font-medium text-slate-500">{block.completeness_pct}%</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={fillAi} loading={Boolean(jobId)}>
            <Sparkles className="h-3.5 w-3.5" />
            Заполнить ИИ
          </Button>
          <Button size="sm" disabled={!dirty} onClick={() => save(content, 'manual')}>
            <Save className="h-3.5 w-3.5" />
            Сохранить
          </Button>
        </div>
      </div>

      <div className="space-y-4 px-5 py-4">
        {draft && (
          <div className="rounded-xl border-2 border-dashed border-brand-300 bg-brand-50/70 p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-brand-800">
                <Sparkles className="h-3.5 w-3.5" />
                Черновик ИИ — проверьте и примените
              </p>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => draft.content && save(draft.content, 'ai')}>
                  <Check className="h-3.5 w-3.5" />
                  Применить
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                  <X className="h-3.5 w-3.5" />
                  Отклонить
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              {schema.fields?.map((f) => {
                const current = field(f.key)
                const proposed = draftField(f.key)
                return (
                  <div key={f.key} className="rounded-lg bg-white px-3 py-2 text-sm">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{f.label}</p>
                    <p className="text-slate-400 line-through">{isFilled(current) ? String(Array.isArray(current) ? current.join('; ') : current) : 'пусто'}</p>
                    <p className="font-medium text-brand-900">
                      {isFilled(proposed) ? String(Array.isArray(proposed) ? (proposed as string[]).join('; ') : proposed) : '—'}
                    </p>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {schema.fields?.map((f) => (
          <div key={f.key}>
            <Label htmlFor={`blk_${block.block_code}_${f.key}`}>
              {f.label}
              {f.required && <span className="ml-1 text-red-400">*</span>}
            </Label>
            {f.type === 'list' ? (
              <ListInput
                values={(field(f.key) as string[]) ?? []}
                onChange={(values) => setField(f.key, values)}
                placeholder="Добавьте пункт и нажмите Enter"
              />
            ) : f.type === 'date' ? (
              <Input
                id={`blk_${block.block_code}_${f.key}`}
                type="date"
                value={(field(f.key) as string) ?? ''}
                onChange={(e) => setField(f.key, e.target.value)}
              />
            ) : f.type === 'textarea' ? (
              <Textarea
                id={`blk_${block.block_code}_${f.key}`}
                rows={2}
                placeholder={f.placeholder}
                value={(field(f.key) as string) ?? ''}
                onChange={(e) => setField(f.key, e.target.value)}
              />
            ) : (
              <Input
                id={`blk_${block.block_code}_${f.key}`}
                placeholder={f.placeholder}
                value={(field(f.key) as string) ?? ''}
                onChange={(e) => setField(f.key, e.target.value)}
              />
            )}
          </div>
        ))}
      </div>

      {dirty && (
        <div className="flex items-center justify-between border-t border-amber-100 bg-amber-50/70 px-5 py-2.5">
          <p className="text-xs text-amber-700">Есть несохраненные правки</p>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setContent(baseline)}>
              Отменить
            </Button>
            <Button size="sm" onClick={() => save(content, 'manual')}>
              Сохранить
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
