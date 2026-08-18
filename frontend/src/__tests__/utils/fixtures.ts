import { ChatMessage, Company, Contract, Product, RequestRecord, RequestTz, TzStage, TzTemplate, TzTemplateSummary } from '@/lib/api'

/** Канонические тестовые фикстуры, соответствующие схемам api/types.ts */

export const companies: Company[] = [
  { company_id: 'C-1', name: 'ГеоСервис', info: null, services: 'ГРП, ГТИ', rating: 5 },
  { company_id: 'C-2', name: 'Бурение-Плюс', info: null, services: 'Бурение', rating: 4 },
]

export const contracts: Contract[] = [
  { contract_id: 'K-1', contract_number: '123-ГП', company_id: 'C-1' },
  { contract_id: 'K-2', contract_number: '456-БП', company_id: 'C-2' },
]

export const products: Product[] = [
  { product_id: 'P-1', product_name: 'Гидравлический разрыв пласта' },
  { product_id: 'P-2', product_name: 'Построение 3D-геомодели' },
]

export const templatesSummary: TzTemplateSummary[] = [
  { id: 'T-1', code: 'PTD', name: 'ТЗ ПТД', description: 'Проект технической документации' },
]

export const template: TzTemplate = {
  id: 'T-1',
  code: 'PTD',
  name: 'ТЗ ПТД',
  description: 'Проект технической документации',
  blocks_schema: {
    blocks: [
      {
        code: 'goals',
        name: 'Цели и задачи работ',
        order: 1,
        fields: [
          { key: 'goal_text', type: 'text', label: 'Цель', required: true },
          { key: 'tasks', type: 'list', label: 'Задачи', required: true },
        ],
      },
      {
        code: 'scope',
        name: 'Периметр работ',
        order: 2,
        fields: [
          { key: 'location', type: 'text', label: 'Место оказания' },
          { key: 'field_name', type: 'text', label: 'Наименование месторождения', required: true },
        ],
      },
      {
        code: 'work_content',
        name: 'Содержание работ',
        order: 3,
        is_stages_block: true,
      },
      {
        code: 'signatures',
        name: 'Подписи сторон',
        order: 4,
        fields: [
          { key: 'customer_signee', type: 'text', label: 'Подписант Заказчика', required: true },
          { key: 'contractor_signee', type: 'text', label: 'Подписант Исполнителя', required: true },
        ],
      },
    ],
  },
  stages: [
    {
      stage_order: 1,
      stage_name: 'Формирование базы данных',
      default_requirements: 'Исходные данные заказчика',
      default_results: 'База данных проекта',
    },
    {
      stage_order: 2,
      stage_name: 'Построение 3D-геомодели',
      default_requirements: 'Геологическая модель',
      default_results: 'Согласованная 3D-модель',
    },
  ],
}

let requestSeq = 0

export function makeRequest(overrides: Partial<RequestRecord> = {}): RequestRecord {
  requestSeq += 1
  const now = new Date().toISOString()
  return {
    id: `req-${requestSeq}`,
    number: `REQ-2026-${String(requestSeq).padStart(6, '0')}`,
    status: 'draft',
    company_id: null,
    contract_id: null,
    product_id: null,
    title: null,
    description: null,
    cost_total: null,
    currency: 'RUB',
    date_start: null,
    date_end: null,
    chat_session_id: null,
    created_at: now,
    updated_at: now,
    ...overrides,
  }
}

export const REQUEST_ID = 'req-e2e-1'
export const CHAT_SESSION_ID = 'sess-1'
export const JOB_ID = 'job-1'

let tzSeq = 0

/** ТЗ по фикстурному шаблону T-1; блоки намеренно не по порядку (проверка сортировки) */
export function makeTz(overrides: Partial<RequestTz> = {}): RequestTz {
  tzSeq += 1
  return {
    tz_id: `tz-${tzSeq}`,
    request_id: REQUEST_ID,
    template_id: 'T-1',
    version: 1,
    completeness_pct: 0,
    payload: {},
    blocks: [
      { block_code: 'signatures', block_name: 'Подписи сторон', content: {}, filled_by: 'manual', is_complete: false, completeness_pct: 0 },
      { block_code: 'goals', block_name: 'Цели и задачи работ', content: {}, filled_by: 'manual', is_complete: false, completeness_pct: 0 },
      { block_code: 'work_content', block_name: 'Содержание работ', content: {}, filled_by: 'manual', is_complete: false, completeness_pct: 0 },
      { block_code: 'scope', block_name: 'Периметр работ', content: {}, filled_by: 'manual', is_complete: false, completeness_pct: 0 },
    ],
    stages: [],
    ...overrides,
  }
}

export function makeStage(overrides: Partial<TzStage> = {}): TzStage {
  const seq = (tzSeq * 100) + (overrides.stage_order ?? 1)
  return {
    id: `stage-${seq}`,
    stage_order: 1,
    stage_name: 'Этап',
    requirements: '',
    expected_results: '',
    description: '',
    stage_start_date: null,
    stage_end_date: null,
    filled_by: 'manual',
    ...overrides,
  }
}

let msgSeq = 0

export function makeChatMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  msgSeq += 1
  return {
    id: `msg-${msgSeq}`,
    role: 'assistant',
    content: 'Ответ ИИ',
    actions: null,
    suggestions: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

/** SSE-тело ответа чата как его отдаёт бэкенд */
export function sseBody(...events: object[]): string {
  return [...events.map((e) => `data: ${JSON.stringify(e)}`), 'data: [DONE]', '', ''].join('\n\n')
}
