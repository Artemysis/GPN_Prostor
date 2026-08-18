import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Coins, Save } from 'lucide-react'
import { api } from '@/lib/api'
import type { RequestRecord } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/controls'
import { FilledByBadge } from '@/components/shared/badges'
import { useUiStore } from '@/lib/stores/uiStore'

/**
 * Оценочная стоимость заявки — сознательно вынесена в конец конструктора ТЗ (а не в шапку
 * заявки): она либо оценивается ИИ по итоговому содержанию ТЗ, либо уточняется пользователем
 * уже после того, как ТЗ заполнено.
 */
export function EstimatedCostCard({ requestId, request }: { requestId: string; request: RequestRecord }) {
  const [value, setValue] = useState(request.cost_total != null ? String(request.cost_total) : '')
  const queryClient = useQueryClient()
  const toast = useUiStore((s) => s.toast)

  useEffect(() => {
    setValue(request.cost_total != null ? String(request.cost_total) : '')
  }, [request.cost_total])

  const filledByAi = request.request_metadata?.filled_by?.cost_total

  const dirty = value !== (request.cost_total != null ? String(request.cost_total) : '')

  const save = () => {
    void api.updateRequest(requestId, { cost_total: value ? Number(value) : null }).then(() => {
      queryClient.invalidateQueries({ queryKey: ['request', requestId] })
      toast('Оценочная стоимость сохранена', 'success')
    })
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/60 px-5 py-3">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-800 text-white">
            <Coins className="h-3.5 w-3.5" />
          </span>
          <p className="flex items-center gap-2 text-sm font-semibold text-slate-800">
            Оценочная стоимость
            <FilledByBadge value={filledByAi === 'ai' ? 'ai' : undefined} />
          </p>
        </div>
        <Button size="sm" disabled={!dirty} onClick={save}>
          <Save className="h-3.5 w-3.5" />
          Сохранить
        </Button>
      </div>
      <div className="px-5 py-4">
        <Label htmlFor="est_cost">Стоимость, ₽</Label>
        <Input
          id="est_cost"
          type="number"
          min={0}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="24 500 000"
        />
        <p className="mt-1.5 text-xs text-slate-400">
          Формируется по итогам заполнения ТЗ — вручную или на основе оценки ИИ (см. вкладку «Анализ»)
        </p>
      </div>
    </Card>
  )
}
