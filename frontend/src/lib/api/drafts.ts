import { uid } from '@/lib/utils'
import type { FilledBy, TzBlockField, TzStage, TzTemplateStageSkeleton } from './types'

export interface DraftContext {
  field_name?: string
  product_name?: string
  template_name?: string
  date_start?: string | null
  date_end?: string | null
}

export function draftBlockContent(blockCode: string, ctx: DraftContext): Record<string, unknown> {
  const field = ctx.field_name ?? 'Ваньгаяхинское'
  switch (blockCode) {
    case 'goals':
      return {
        goal_text: `Актуализация геологической информации и подсчет запасов ${field} месторождения`,
        tasks: [
          'Актуализировать базу геолого-промысловых данных',
          'Выполнить литолого-стратиграфическое расчленение разреза',
          'Построить 3D геологическую модель',
          'Подготовить отчет по подсчету запасов',
        ],
      }
    case 'scope':
      return { location: 'г. Тюмень', field_name: field }
    case 'terms':
      return { date_start: ctx.date_start ?? '2026-01-12', date_end: ctx.date_end ?? '2026-12-25' }
    case 'conditions':
      return {
        source_data: 'Данные отчетов по ПЗ/ОПЗ, результаты испытаний, сейсмические исследования 3D',
        software: 'Isoline, T-Navigator/Petrel',
      }
    case 'documentation':
      return { report_formats: 'DOC/DOCX, PDF, XLS/XLSX' }
    case 'quality_control':
      return { acceptance: 'Приемка каждого этапа с актом сдачи-приемки, экспертная оценка Заказчика' }
    case 'signatures':
      return { customer_signee: 'Иванов И.И., ведущий геолог НТЦ', contractor_signee: 'Петров П.П., заместитель директора' }
    default:
      return {}
  }
}

export function draftStages(skeleton: TzTemplateStageSkeleton[], filledBy: FilledBy = 'ai'): TzStage[] {
  return skeleton.map((s) => ({
    id: uid('stg_'),
    stage_order: s.stage_order,
    stage_name: s.stage_name,
    requirements: s.default_requirements ?? '',
    expected_results: s.default_results ?? '',
    description: '',
    stage_start_date: null,
    stage_end_date: null,
    filled_by: filledBy,
  }))
}

export function isFilled(value: unknown): boolean {
  if (value == null) return false
  if (typeof value === 'string') return value.trim().length > 0
  if (Array.isArray(value)) return value.length > 0
  return true
}

export function computeBlockPct(
  fields: TzBlockField[] | undefined,
  content: Record<string, unknown>,
  isStagesBlock?: boolean,
  stages?: TzStage[],
): number {
  if (isStagesBlock) {
    if (!stages || stages.length === 0) return 0
    const perStage = stages.map((s) => {
      let score = 0
      if (isFilled(s.stage_name)) score += 0.4
      if (isFilled(s.requirements)) score += 0.3
      if (isFilled(s.expected_results)) score += 0.3
      return score
    })
    const avg = perStage.reduce((a, b) => a + b, 0) / stages.length
    return Math.round((avg * stages.length >= stages.length * 0.9 ? 1 : 0.6 + avg * 0.4) * 100)
  }
  if (!fields || fields.length === 0) return 0
  let total = 0
  let filled = 0
  for (const f of fields) {
    const w = f.required ? 2 : 1
    total += w
    if (isFilled(content[f.key])) filled += w
  }
  return Math.round((filled / total) * 100)
}

export function computeTzPct(blocks: { completeness_pct: number }[]): number {
  if (blocks.length === 0) return 0
  return Math.round(blocks.reduce((a, b) => a + b.completeness_pct, 0) / blocks.length)
}
