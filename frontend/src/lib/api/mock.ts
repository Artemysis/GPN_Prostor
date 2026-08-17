import { delay, monthsBetween, uid } from '@/lib/utils'
import { seedDb, type Db } from './data'
import { computeBlockPct, computeTzPct, draftBlockContent, draftStages, isFilled } from './drafts'
import type {
  AppliedDiff,
  ChatAction,
  ChatEvent,
  ChatMessage,
  ChatSession,
  DocumentKind,
  DocumentRecord,
  FilledBy,
  Job,
  RequestRecord,
  RequestTz,
  TzAnalysis,
  TzStage,
  TzTemplate,
} from './types'

const DB_KEY = 'prostor.db.v1'

let db: Db = load()

function load(): Db {
  try {
    const raw = localStorage.getItem(DB_KEY)
    if (raw) return JSON.parse(raw) as Db
  } catch {
    void 0
  }
  const fresh = seedDb()
  persist(fresh)
  return fresh
}

function persist(next: Db = db) {
  try {
    localStorage.setItem(DB_KEY, JSON.stringify(next))
  } catch {
    void 0
  }
}

function nowIso(): string {
  return new Date().toISOString()
}

function toB64(s: string): string {
  return btoa(String.fromCharCode(...new TextEncoder().encode(s)))
}

function fromB64(b: string): string {
  return new TextDecoder().decode(Uint8Array.from(atob(b), (c) => c.charCodeAt(0)))
}

function runJob(type: Job['type'], exec: () => unknown, duration = 1800): Job {
  const job: Job = { id: uid('job_'), type, status: 'pending', result: null, error: null }
  db.jobs.push(job)
  persist()
  setTimeout(() => {
    job.status = 'running'
    persist()
  }, 350)
  setTimeout(() => {
    try {
      job.result = exec()
      job.status = 'done'
    } catch (e) {
      job.status = 'failed'
      job.error = e instanceof Error ? e.message : String(e)
    }
    persist()
  }, duration + Math.random() * 700)
  return job
}

function getTemplate(id: string): TzTemplate {
  const tpl = db.templates.find((t) => t.id === id)
  if (!tpl) throw new Error('Шаблон ТЗ не найден')
  return tpl
}

function getTz(requestId: string): RequestTz {
  const tz = db.tzs.find((t) => t.request_id === requestId)
  if (!tz) throw new Error('ТЗ не найдено')
  return tz
}

function getRequest(id: string): RequestRecord {
  const req = db.requests.find((r) => r.id === id)
  if (!req) throw new Error('Заявка не найдена')
  return req
}

function refreshTz(tz: RequestTz): RequestTz {
  const tpl = getTemplate(tz.template_id)
  for (const block of tz.blocks) {
    const schema = tpl.blocks_schema.blocks.find((b) => b.code === block.block_code)
    block.completeness_pct = computeBlockPct(schema?.fields, block.content, schema?.is_stages_block, tz.stages)
    block.is_complete = block.completeness_pct >= 100
  }
  tz.completeness_pct = computeTzPct(tz.blocks)
  persist()
  return tz
}

interface ChatReply {
  text: string
  suggestions:
    | {
        products?: { product_id: string; product_name: string; justification: string }[]
        contractors?: { company_id: string; name: string; rating: number; justification: string }[]
        similar_requests?: { request_id: string; title: string; similarity: number; status: RequestRecord['status'] }[]
      }
    | null
  actions: ChatAction[]
}

interface Intent {
  keywords: RegExp
  templateCode: string
  productIds: string[]
  contractorIds: string[]
  cost: number
  intentLabel: string
}

const intents: Intent[] = [
  {
    keywords: /запас|3d|3-d|геомодел|геолог|петрофиз|литолог/i,
    templateCode: 'concept_geology',
    productIds: ['p_geology', 'p_reserves'],
    contractorIds: ['c_nng', 'c_ntc'],
    cost: 24500000,
    intentLabel: 'подсчет запасов / геомоделирование',
  },
  {
    keywords: /заканчив|бур|скважин|гти|креплен|перфорац/i,
    templateCode: 'concept_completion',
    productIds: ['p_completion', 'p_ptd_nng'],
    contractorIds: ['c_tnnc', 'c_nng'],
    cost: 31200000,
    intentLabel: 'заканчивание и строительство скважин',
  },
  {
    keywords: /обустройств|инфраструктур|трубо|сбор|энерг|тэо/i,
    templateCode: 'concept_facilities',
    productIds: ['p_facilities'],
    contractorIds: ['c_ural', 'c_ntc'],
    cost: 18700000,
    intentLabel: 'обустройство и инфраструктура',
  },
  {
    keywords: /разработ|развит|дренир|мун|гдм|добыч/i,
    templateCode: 'concept_development',
    productIds: ['p_development'],
    contractorIds: ['c_ntc', 'c_sibnk'],
    cost: 42800000,
    intentLabel: 'концепт разработки / развития',
  },
  {
    keywords: /нового мест|поисков|разведк|пз|оценочн/i,
    templateCode: 'pz_new',
    productIds: ['p_pz'],
    contractorIds: ['c_ntc', 'c_sibnk'],
    cost: 26400000,
    intentLabel: 'поисково-оценочные работы',
  },
  {
    keywords: /птд|проектно-технолог|сопровожд|высокорисков/i,
    templateCode: 'ptd_nng',
    productIds: ['p_ptd_nng', 'p_engineering'],
    contractorIds: ['c_tnnc'],
    cost: 9800000,
    intentLabel: 'ПТД и сопровождение работ',
  },
]

function detectIntent(content: string): Intent | null {
  for (const intent of intents) {
    if (intent.keywords.test(content)) return intent
  }
  return null
}

function buildReply(session: ChatSession, content: string): ChatReply {
  const lower = content.toLowerCase()

  if (/альтернатив/i.test(lower)) {
    const products = db.products.slice(0, 4).map((p) => ({
      product_id: p.product_id,
      product_name: p.product_name,
      justification: 'Альтернатива с частичным покрытием потребности',
    }))
    return {
      text: 'Вот альтернативные варианты продуктов. Сравните их с первоначальным предложением: у каждого — свой периметр работ и стоимость. Если нужно, углублюсь в отличия или предложу комбинацию услуг. Решение остается за вами.',
      suggestions: { products },
      actions: [],
    }
  }

  if (/согласен|подтвержда|да, |окей|принима/i.test(lower)) {
    return {
      text: 'Отлично. Я ничего не применяю сам: нажмите «Применить выбранные» под предложениями ниже, чтобы заполнить шапку заявки. После этого можно создать ТЗ из рекомендованного шаблона.',
      suggestions: null,
      actions: [],
    }
  }

  if (/объясни|риск|почему|как счита/i.test(lower)) {
    return {
      text: 'Анализ качества ТЗ работает по бизнес-правилам: обязательность объекта работ (scope.field_name), наличие этапа подготовки исходных данных при построении 3D-модели, соответствие срока типовомУ (12 мес.), отражение операций продукта в содержании работ и наличие подписантов. ИИ формулирует риски и рекомендации, а устранять их или нет — решаете вы.',
      suggestions: null,
      actions: [],
    }
  }

  const intent = detectIntent(content)
  const chosen = intent ?? intents[0]
  const tpl = db.templates.find((t) => t.code === chosen.templateCode) ?? db.templates[0]
  const products = chosen.productIds
    .map((id) => db.products.find((p) => p.product_id === id))
    .filter((p): p is NonNullable<typeof p> => Boolean(p))
    .map((p, i) => ({
      product_id: p.product_id,
      product_name: p.product_name,
      justification: i === 0 ? 'Точное соответствие запросу, полный периметр работ' : 'Смежная услуга, частично покрывает потребность',
    }))
  const contractors = chosen.contractorIds
    .map((id) => db.companies.find((c) => c.company_id === id))
    .filter((c): c is NonNullable<typeof c> => Boolean(c))
    .map((c, i) => ({
      company_id: c.company_id,
      name: c.name,
      rating: c.rating,
      justification: i === 0 ? `Рейтинг ${c.rating}, профильные услуги: ${c.services.split(',')[0].toLowerCase()}` : 'Опыт аналогичных работ по договору',
    }))
  const similar = db.requests
    .filter((r) => r.id !== session.request_id)
    .slice(0, 2)
    .map((r, i) => ({ request_id: r.id, title: r.title, similarity: 0.87 - i * 0.16, status: r.status }))

  const actions: ChatAction[] = [
    {
      type: 'set_field',
      field: 'product_id',
      value: products[0]?.product_id,
      confidence: 0.92,
      justification: products[0]?.justification,
    },
    {
      type: 'set_field',
      field: 'company_id',
      value: contractors[0]?.company_id,
      confidence: 0.9,
      justification: contractors[0]?.justification,
    },
    {
      type: 'set_field',
      field: 'cost_total',
      value: String(chosen.cost),
      confidence: 0.72,
      justification: 'Оценка по аналогичным выполненным заявкам',
    },
    { type: 'suggest_template', template_id: tpl.id, code: tpl.code, confidence: intent ? 0.9 : 0.62 },
  ]

  const intro = intent
    ? `Классифицировал намерение: ${chosen.intentLabel}.`
    : 'Точную категорию определить не удалось, поэтому предлагаю наиболее универсальный вариант — уточните вводные, и я скорректирую подбор.'

  const text = [
    intro,
    `Продукты: ${products.map((p) => `«${p.product_name}»`).join(', ')}.`,
    `Подрядчики: ${contractors.map((c) => `${c.name} (рейтинг ${c.rating})`).join('; ')}.`,
    similar.length > 0 ? `Аналогичные заявки: ${similar.map((s) => `«${s.title}» (${Math.round(s.similarity * 100)}%)`).join(', ')}.` : '',
    'Все предложения — черновики. Примените подходящие кнопками ниже или обсудим варианты: могу предложить альтернативы, обосновать выбор, скорректировать стоимость.',
  ]
    .filter(Boolean)
    .join('\n')

  return { text, suggestions: { products, contractors, similar_requests: similar }, actions }
}

function analyzeTz(tz: RequestTz, req: RequestRecord): TzAnalysis {
  const risks: TzAnalysis['risks'] = []
  const recommendations: TzAnalysis['recommendations'] = []
  const block = (code: string) => tz.blocks.find((b) => b.block_code === code)
  const str = (code: string, key: string) => String((block(code)?.content?.[key] as string | undefined) ?? '')

  if (!isFilled(str('scope', 'field_name'))) {
    risks.push({
      severity: 'high',
      category: 'missing_data',
      title: 'Не указан объект работ',
      description: 'Поле scope.field_name пусто',
      suggestion: 'Укажите наименование месторождения',
      block_code: 'scope',
    })
  }

  const fullText = JSON.stringify(tz.blocks.map((b) => b.content)).toLowerCase() + ' ' + tz.stages.map((s) => s.stage_name).join(' ').toLowerCase()
  const has3d = fullText.includes('3d') || fullText.includes('геомодел')
  const stageNames = tz.stages.map((s) => s.stage_name.toLowerCase()).join(' ')
  if (has3d && !/баз[ыа] данных|исходных данных/.test(stageNames)) {
    risks.push({
      severity: 'high',
      category: 'logical',
      title: '3D-модель без этапа подготовки исходных данных',
      description: 'Указано построение 3D-геомодели, но отсутствует этап формирования базы данных',
      suggestion: 'Добавить этап 1 «Формирование базы данных»',
      block_code: 'work_content',
    })
    recommendations.push({
      title: 'Указать требования к 3D-модели',
      description: 'Добавить раздел требований к 3D-модели в содержание работ',
      priority: 2,
      block_code: 'work_content',
    })
  }

  const months = monthsBetween(str('terms', 'date_start') || req.date_start, str('terms', 'date_end') || req.date_end)
  if (months > 0 && months < 12) {
    risks.push({
      severity: 'medium',
      category: 'terms',
      title: 'Заявленный срок ниже типового',
      description: `Срок работ ${months} мес., типовой для этого типа работ — 12 мес.`,
      suggestion: 'Проверить календарный план',
      block_code: 'terms',
    })
    recommendations.push({
      title: 'Проверить календарный план',
      description: 'Срок работ ниже типового для данного типа ТЗ',
      priority: 3,
      block_code: 'terms',
    })
  }

  if (req.product_id) {
    const ops = db.product_operations.filter((o) => o.product_id === req.product_id).slice(0, 3)
    if (ops.length > 0 && tz.stages.length > 0) {
      const missing = ops.filter((o) => !stageNames.includes(o.operation_name.toLowerCase().slice(0, 12)))
      if (missing.length > 1) {
        risks.push({
          severity: 'low',
          category: 'compliance',
          title: 'Операции продукта не отражены в содержании работ',
          description: `Не найдено отражение операций: ${missing.map((m) => m.operation_name).join(', ')}`,
          suggestion: 'Добавить этапы или требования по операциям продукта',
          block_code: 'work_content',
        })
      }
    }
  }

  if (!isFilled(str('signatures', 'customer_signee')) && !isFilled(str('signatures', 'contractor_signee'))) {
    risks.push({
      severity: 'low',
      category: 'missing_data',
      title: 'Не указаны подписанты сторон',
      description: 'Блок signatures пустой',
      suggestion: 'Заполнить подписантов Заказчика и Исполнителя',
      block_code: 'signatures',
    })
  }

  if (!isFilled(str('conditions', 'source_data'))) {
    recommendations.push({
      title: 'Добавить исходные данные',
      description: 'Перед согласованием необходимо добавить требования к исходным материалам',
      priority: 1,
      block_code: 'conditions',
    })
  }

  return {
    completeness_pct: tz.completeness_pct,
    block_completeness: Object.fromEntries(tz.blocks.map((b) => [b.block_code, b.completeness_pct])),
    risks,
    recommendations: recommendations.sort((a, b) => a.priority - b.priority),
    analyzed_at: nowIso(),
  }
}

function renderTzText(tz: RequestTz, tpl: TzTemplate, req: RequestRecord): string {
  const lines: string[] = [`ТЕХНИЧЕСКОЕ ЗАДАНИЕ (${tpl.name})`, `Заявка ${req.number}: ${req.title}`, '']
  for (const b of tz.blocks) {
    lines.push(`${b.block_name}`)
    if (b.block_code === 'work_content') {
      for (const s of tz.stages) {
        lines.push(`  ${s.stage_order}. ${s.stage_name}`)
        if (s.requirements) lines.push(`     Требования: ${s.requirements}`)
        if (s.expected_results) lines.push(`     Ожидаемые результаты: ${s.expected_results}`)
      }
    } else {
      for (const [k, v] of Object.entries(b.content)) {
        lines.push(`  ${k}: ${Array.isArray(v) ? v.join('; ') : String(v)}`)
      }
    }
    lines.push('')
  }
  lines.push(`Готовность: ${tz.completeness_pct}%`)
  return lines.join('\n')
}

function renderReportText(tz: RequestTz, req: RequestRecord, analysis: TzAnalysis | undefined): string {
  const lines = [
    'АНАЛИТИЧЕСКИЙ ОТЧЕТ (сгенерирован ИИ)',
    `Заявка ${req.number}: ${req.title}`,
    `Готовность ТЗ: ${tz.completeness_pct}%`,
    '',
    '1. Сводка',
    `Сформировано ТЗ из ${tz.blocks.length} блоков, этапов работ: ${tz.stages.length}.`,
    '',
    '2. Качество ТЗ',
    ...(analysis ? Object.entries(analysis.block_completeness).map(([k, v]) => `  ${k}: ${v}%`) : ['  Анализ не проводился.']),
    '',
    '3. Риски',
    ...(analysis && analysis.risks.length > 0
      ? analysis.risks.map((r) => `  [${r.severity}] ${r.title} — ${r.description}`)
      : ['  Риски не выявлены.']),
    '',
    '4. Рекомендации',
    ...(analysis && analysis.recommendations.length > 0
      ? analysis.recommendations.map((r) => `  ${r.priority}. ${r.title}: ${r.description}`)
      : ['  Нет рекомендаций.']),
    '',
    'Отчет носит рекомендательный характер. Решения принимает руководитель работ Заказчика.',
  ]
  return lines.join('\n')
}

function makeDocument(requestId: string, kind: DocumentKind, filename: string, mime: string, content: string, generatedByAi: boolean): DocumentRecord {
  const doc: DocumentRecord = {
    id: uid('doc_'),
    request_id: requestId,
    kind,
    filename,
    mime_type: mime,
    size_bytes: new Blob([content]).size,
    generated_by_ai: generatedByAi,
    created_at: nowIso(),
    data_base64: toB64(content),
  }
  db.documents.push(doc)
  return doc
}

export const mockApi = {
  reset() {
    localStorage.removeItem(DB_KEY)
    db = seedDb()
    persist()
  },

  login(username: string): { access_token: string; user: Db['users'][number] } {
    const user =
      db.users.find((u) => u.username === username) ??
      ({ id: uid('u_'), username, full_name: username, role: 'customer' } as Db['users'][number])
    return { access_token: uid('jwt_'), user }
  },

  listCompanies(search?: string): Db['companies'] {
    let items = [...db.companies]
    if (search) items = items.filter((c) => (c.name + c.services).toLowerCase().includes(search.toLowerCase()))
    return items
  },
  getCompany(id: string) {
    const company = db.companies.find((c) => c.company_id === id)
    if (!company) throw new Error('Компания не найдена')
    return { ...company, contracts: db.contracts.filter((k) => k.company_id === id) }
  },
  listContracts(companyId?: string): Db['contracts'] {
    return companyId ? db.contracts.filter((k) => k.company_id === companyId) : [...db.contracts]
  },
  listProducts(contractId?: string): Db['products'] {
    if (!contractId) return [...db.products]
    const ids = db.contract_products.filter((cp) => cp.contract_id === contractId).map((cp) => cp.product_id)
    return db.products.filter((p) => ids.includes(p.product_id))
  },
  getProductRates(productId: string): Db['product_rates'] {
    return db.product_rates.filter((r) => r.product_id === productId)
  },
  getProductOperations(productId: string): Db['product_operations'] {
    return db.product_operations.filter((o) => o.product_id === productId).sort((a, b) => a.operation_order - b.operation_order)
  },
  listCalculations(contractId?: string): Db['cost_calculations'] {
    return contractId ? db.cost_calculations.filter((c) => c.contract_id === contractId) : [...db.cost_calculations]
  },
  listCalculationStages(calcId: string): Db['calculation_stages'] {
    return db.calculation_stages.filter((s) => s.calc_id === calcId).sort((a, b) => a.stage_order_num - b.stage_order_num)
  },

  listTemplates(): { id: string; code: string; name: string; description: string }[] {
    return db.templates.map(({ id, code, name, description }) => ({ id, code, name, description }))
  },
  getTemplate(id: string): TzTemplate {
    return getTemplate(id)
  },
  recommendTemplate(prompt: string) {
    const intent = detectIntent(prompt)
    const tpl = intent ? db.templates.find((t) => t.code === intent.templateCode) : db.templates[0]
    if (!tpl) throw new Error('Шаблоны не загружены')
    return {
      template_id: tpl.id,
      code: tpl.code,
      name: tpl.name,
      confidence: intent ? 0.9 : 0.55,
      justification: intent ? `Запрос соответствует типу «${tpl.name}»` : 'Универсальная форма ТЗ',
      suggested_fields: { goals: ['Актуализация геологической информации'] },
    }
  },

  createRequest(input: { title?: string; description?: string }): RequestRecord {
    const num = `REQ-2026-${String(db.counters.request).padStart(4, '0')}`
    db.counters.request += 1
    const req: RequestRecord = {
      id: uid('r_'),
      number: num,
      user_id: 'u_demo',
      status: 'draft',
      company_id: null,
      contract_id: null,
      product_id: null,
      title: input.title?.trim() || 'Новая заявка',
      description: input.description ?? '',
      cost_total: null,
      currency: 'RUB',
      date_start: null,
      date_end: null,
      chat_session_id: null,
      filled_by: {},
      created_at: nowIso(),
      updated_at: nowIso(),
    }
    db.requests.unshift(req)
    persist()
    return req
  },
  listRequests(status?: string): RequestRecord[] {
    const items = [...db.requests].sort((a, b) => b.created_at.localeCompare(a.created_at))
    return status ? items.filter((r) => r.status === status) : items
  },
  getRequest(id: string): RequestRecord & { tz_summary: { completeness_pct: number; risks_count: number }; documents_count: number } {
    const req = getRequest(id)
    const tz = db.tzs.find((t) => t.request_id === id)
    const analysis = tz ? db.analyses.find((a) => a.tz_id === tz.tz_id) : undefined
    return {
      ...req,
      tz_summary: {
        completeness_pct: tz?.completeness_pct ?? 0,
        risks_count: analysis?.risks.length ?? 0,
      },
      documents_count: db.documents.filter((d) => d.request_id === id).length,
    }
  },
  updateRequest(id: string, patch: Partial<RequestRecord>): RequestRecord {
    const req = getRequest(id)
    Object.assign(req, patch, { updated_at: nowIso() })
    persist()
    return req
  },
  deleteRequest(id: string) {
    db.requests = db.requests.filter((r) => r.id !== id)
    db.tzs = db.tzs.filter((t) => t.request_id !== id)
    db.documents = db.documents.filter((d) => d.request_id !== id)
    persist()
  },
  submitRequest(id: string): RequestRecord {
    const req = getRequest(id)
    req.status = 'submitted'
    req.updated_at = nowIso()
    persist()
    return req
  },

  createTz(requestId: string, templateId: string, prefill = false): RequestTz {
    const existing = db.tzs.find((t) => t.request_id === requestId)
    if (existing) return existing
    const tpl = getTemplate(templateId)
    const req = getRequest(requestId)
    const ctx = { field_name: req.title.split(',')[1]?.trim().replace('месторождение', '').trim(), template_name: tpl.name, date_start: req.date_start, date_end: req.date_end }
    const blocks = tpl.blocks_schema.blocks.map((b) => {
      const content: Record<string, unknown> = {}
      let filled: FilledBy = 'manual'
      if (prefill) {
        if (b.code === 'terms' && (req.date_start || req.date_end)) {
          Object.assign(content, draftBlockContent('terms', ctx))
          filled = 'ai'
        }
        if (b.code === 'goals') {
          Object.assign(content, { goal_text: req.title, tasks: [] })
          filled = 'ai'
        }
      }
      return {
        block_code: b.code,
        block_name: b.name,
        content,
        filled_by: filled,
        is_complete: false,
        completeness_pct: 0,
      }
    })
    const tz: RequestTz = {
      tz_id: uid('tz_'),
      request_id: requestId,
      template_id: templateId,
      version: 1,
      completeness_pct: 0,
      blocks,
      stages: [],
    }
    db.tzs.push(tz)
    if (req.status === 'draft') req.status = 'in_progress'
    req.updated_at = nowIso()
    refreshTz(tz)
    return tz
  },
  getTz(requestId: string): RequestTz | null {
    return db.tzs.find((t) => t.request_id === requestId) ?? null
  },
  saveBlock(requestId: string, blockCode: string, content: Record<string, unknown>, filledBy: FilledBy): RequestTz {
    const tz = getTz(requestId)
    const block = tz.blocks.find((b) => b.block_code === blockCode)
    if (!block) throw new Error('Блок не найден')
    const prev = block.filled_by
    block.content = content
    block.filled_by = prev === 'ai' && filledBy === 'manual' ? 'mixed' : filledBy
    return refreshTz(tz)
  },
  addStage(requestId: string, stage: Partial<TzStage> & { stage_name: string }): TzStage {
    const tz = getTz(requestId)
    const st: TzStage = {
      id: uid('stg_'),
      stage_order: stage.stage_order ?? tz.stages.length + 1,
      stage_name: stage.stage_name,
      requirements: stage.requirements ?? '',
      expected_results: stage.expected_results ?? '',
      description: stage.description ?? '',
      stage_start_date: stage.stage_start_date ?? null,
      stage_end_date: stage.stage_end_date ?? null,
      filled_by: stage.filled_by ?? 'manual',
    }
    tz.stages.push(st)
    tz.stages.sort((a, b) => a.stage_order - b.stage_order)
    refreshTz(tz)
    return st
  },
  updateStage(requestId: string, stageId: string, patch: Partial<TzStage>): void {
    const tz = getTz(requestId)
    const st = tz.stages.find((s) => s.id === stageId)
    if (!st) throw new Error('Этап не найден')
    Object.assign(st, patch)
    tz.stages.sort((a, b) => a.stage_order - b.stage_order)
    refreshTz(tz)
  },
  deleteStage(requestId: string, stageId: string): void {
    const tz = getTz(requestId)
    tz.stages = tz.stages.filter((s) => s.id !== stageId)
    tz.stages.forEach((s, i) => (s.stage_order = i + 1))
    refreshTz(tz)
  },

  startFillAi(requestId: string, blockCode: string): Job {
    return runJob(
      'fill_ai',
      () => {
        const tz = getTz(requestId)
        const tpl = getTemplate(tz.template_id)
        const req = getRequest(requestId)
        const ctx = {
          field_name: String((tz.blocks.find((b) => b.block_code === 'scope')?.content.field_name as string) ?? ''),
          product_name: db.products.find((p) => p.product_id === req.product_id)?.product_name,
          template_name: tpl.name,
          date_start: req.date_start,
          date_end: req.date_end,
        }
        if (blockCode === 'work_content' || blockCode === 'all') {
          return { block_code: 'work_content', stages: draftStages(tpl.stages, 'ai') }
        }
        return { block_code: blockCode, content: draftBlockContent(blockCode, ctx) }
      },
      1500,
    )
  },

  startAnalyze(requestId: string): Job {
    return runJob(
      'analyze',
      () => {
        const tz = getTz(requestId)
        const req = getRequest(requestId)
        const analysis = { ...analyzeTz(tz, req), tz_id: tz.tz_id }
        db.analyses = db.analyses.filter((a) => a.tz_id !== tz.tz_id)
        db.analyses.unshift(analysis)
        return analysis
      },
      2200,
    )
  },
  getAnalysis(requestId: string): TzAnalysis | null {
    const tz = db.tzs.find((t) => t.request_id === requestId)
    if (!tz) return null
    const stored = db.analyses.find((a) => a.tz_id === tz.tz_id)
    return stored ?? null
  },
  getCompleteness(requestId: string) {
    const tz = db.tzs.find((t) => t.request_id === requestId)
    if (!tz) return { completeness_pct: 0, block_completeness: {} as Record<string, number> }
    return {
      completeness_pct: tz.completeness_pct,
      block_completeness: Object.fromEntries(tz.blocks.map((b) => [b.block_code, b.completeness_pct])),
    }
  },

  getOrCreateChatSession(requestId: string): ChatSession {
    const existing = db.chat_sessions.find((s) => s.request_id === requestId)
    if (existing) return existing
    const req = getRequest(requestId)
    const session: ChatSession = {
      id: uid('s_'),
      request_id: requestId,
      title: req.title,
      created_at: nowIso(),
    }
    db.chat_sessions.push(session)
    req.chat_session_id = session.id
    persist()
    return session
  },
  getChatMessages(sessionId: string): ChatMessage[] {
    return db.chat_messages.filter((m) => m.session_id === sessionId)
  },

  async streamChat(sessionId: string, content: string, onEvent: (e: ChatEvent) => void): Promise<void> {
    const session = db.chat_sessions.find((s) => s.id === sessionId)
    if (!session) throw new Error('Сессия не найдена')
    const userMsg: ChatMessage = {
      id: uid('m_'),
      session_id: sessionId,
      role: 'user',
      content,
      actions: null,
      suggestions: null,
      created_at: nowIso(),
    }
    db.chat_messages.push(userMsg)
    persist()

    await delay(350)
    const reply = buildReply(session, content)
    const words = reply.text.split(/(\s+)/)
    for (const w of words) {
      if (w.length === 0) continue
      onEvent({ type: 'delta', content: w })
      await delay(16 + Math.random() * 22)
    }
    const sug = reply.suggestions
    if (sug?.products?.length) {
      onEvent({ type: 'products', items: sug.products })
      await delay(220)
    }
    if (sug?.contractors?.length) {
      onEvent({ type: 'contractors', items: sug.contractors })
      await delay(220)
    }
    if (sug?.similar_requests?.length) {
      onEvent({ type: 'similar_requests', items: sug.similar_requests })
      await delay(180)
    }
    if (reply.actions.length > 0) {
      onEvent({ type: 'actions', actions: reply.actions })
      await delay(120)
    }
    onEvent({ type: 'done' })

    const assistantMsg: ChatMessage = {
      id: uid('m_'),
      session_id: sessionId,
      role: 'assistant',
      content: reply.text,
      actions: reply.actions.length > 0 ? reply.actions : null,
      suggestions: reply.suggestions,
      created_at: nowIso(),
    }
    db.chat_messages.push(assistantMsg)
    persist()
  },

  applyActions(sessionId: string, actions: ChatAction[]): AppliedDiff[] {
    const session = db.chat_sessions.find((s) => s.id === sessionId)
    if (!session || !session.request_id) return []
    const req = getRequest(session.request_id)
    const applied: AppliedDiff[] = []
    for (const action of actions) {
      if (action.type !== 'set_field' || !action.field || action.value === undefined || action.applied) continue
      const oldValue = req[action.field as keyof RequestRecord]
      const value = action.field === 'cost_total' ? Number(action.value) : action.value
      ;(req as unknown as Record<string, unknown>)[action.field] = value
      req.filled_by[action.field] = 'ai'
      if (action.field === 'company_id') {
        req.contract_id = null
      }
      if (action.field === 'contract_id') {
        req.product_id = null
      }
      applied.push({ field: action.field, old: oldValue == null ? '—' : String(oldValue), new: String(value) })
      action.applied = true
    }
    req.updated_at = nowIso()
    persist()
    return applied
  },

  startExport(requestId: string, formats: string[], includeAnalyticalReport: boolean): Job {
    return runJob(
      'export',
      () => {
        const tz = getTz(requestId)
        const tpl = getTemplate(tz.template_id)
        const req = getRequest(requestId)
        const analysis = db.analyses.find((a) => a.tz_id === tz.tz_id)
        const created: DocumentRecord[] = []
        if (formats.includes('docx')) {
          created.push(
            makeDocument(
              requestId,
              'tz_final',
              `ТЗ_${req.number}_${tpl.name.replace(/[ТтЗз ]/g, '')}.docx`,
              'application/msword',
              renderTzText(tz, tpl, req),
              false,
            ),
          )
        }
        if (formats.includes('pdf')) {
          created.push(makeDocument(requestId, 'tz_final', `ТЗ_${req.number}.pdf`, 'application/pdf', renderTzText(tz, tpl, req), false))
        }
        if (includeAnalyticalReport) {
          created.push(
            makeDocument(
              requestId,
              'analytical_report',
              `Аналитический_отчет_${req.number}.docx`,
              'application/msword',
              renderReportText(tz, req, analysis),
              true,
            ),
          )
        }
        return { documents: created.map((d) => d.id) }
      },
      2000,
    )
  },
  listDocuments(requestId: string): DocumentRecord[] {
    return db.documents.filter((d) => d.request_id === requestId).sort((a, b) => b.created_at.localeCompare(a.created_at))
  },
  downloadDocument(docId: string) {
    const doc = db.documents.find((d) => d.id === docId)
    if (!doc) throw new Error('Документ не найден')
    const content = doc.data_base64 ? fromB64(doc.data_base64) : `Файл ${doc.filename} (мок-данные)`
    const blob = new Blob([content], { type: doc.mime_type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = doc.filename
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 5000)
  },
  async uploadAttachment(requestId: string, file: File, kind: DocumentKind = 'attachment'): Promise<DocumentRecord> {
    await delay(500)
    let data_base64: string | undefined
    if (file.size <= 2 * 1024 * 1024) {
      data_base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(toB64(String(reader.result)))
        reader.onerror = () => reject(reader.error)
        reader.readAsText(file)
      })
    }
    const doc: DocumentRecord = {
      id: uid('doc_'),
      request_id: requestId,
      kind,
      filename: file.name,
      mime_type: file.type || 'application/octet-stream',
      size_bytes: file.size,
      generated_by_ai: false,
      created_at: nowIso(),
      data_base64,
    }
    db.documents.push(doc)
    persist()
    return doc
  },
  deleteAttachment(docId: string) {
    db.documents = db.documents.filter((d) => d.id !== docId)
    persist()
  },

  getJob(id: string): Job {
    const job = db.jobs.find((j) => j.id === id)
    if (!job) throw new Error('Задача не найдена')
    return job
  },

  getAnalyticsTz() {
    const byTypeMap = new Map<string, number>()
    const stageCount = new Map<string, number>()
    for (const tz of db.tzs) {
      const tpl = db.templates.find((t) => t.id === tz.template_id)
      const name = tpl?.name ?? '—'
      byTypeMap.set(name, (byTypeMap.get(name) ?? 0) + 1)
      for (const s of tz.stages) {
        const key = s.stage_name.replace(/^Этап \d+\.\s*/, '').slice(0, 48)
        stageCount.set(key, (stageCount.get(key) ?? 0) + 1)
      }
    }
    const errorCount = new Map<string, number>()
    for (const a of db.analyses) {
      for (const r of a.risks) {
        errorCount.set(r.title, (errorCount.get(r.title) ?? 0) + 1)
      }
    }
    const avg = db.tzs.length > 0 ? Math.round(db.tzs.reduce((acc, t) => acc + t.completeness_pct, 0) / db.tzs.length) : 0
    return {
      total_tz: db.tzs.length,
      avg_completeness: avg,
      by_type: [...byTypeMap.entries()].map(([type, count]) => ({ type, count })).sort((a, b) => b.count - a.count),
      by_stage_popularity: [...stageCount.entries()].map(([stage, count]) => ({ stage, count })).sort((a, b) => b.count - a.count).slice(0, 8),
      typical_errors: [...errorCount.entries()].map(([title, count]) => ({ title, count })).sort((a, b) => b.count - a.count).slice(0, 6),
    }
  },
  getAnalyticsSearch() {
    const serviceCount = new Map<string, number>()
    const contractorCount = new Map<string, number>()
    for (const r of db.requests) {
      if (r.product_id) {
        const p = db.products.find((x) => x.product_id === r.product_id)
        if (p) serviceCount.set(p.product_name, (serviceCount.get(p.product_name) ?? 0) + 1)
      }
      if (r.company_id) {
        const c = db.companies.find((x) => x.company_id === r.company_id)
        if (c) contractorCount.set(c.name, (contractorCount.get(c.name) ?? 0) + 1)
      }
    }
    const unfilled = new Map<string, number>()
    for (const tz of db.tzs) {
      const tpl = db.templates.find((t) => t.id === tz.template_id)
      for (const block of tz.blocks) {
        const schema = tpl?.blocks_schema.blocks.find((b) => b.code === block.block_code)
        if (block.block_code === 'work_content') {
          if (tz.stages.length === 0) unfilled.set('Содержание работ (этапы)', (unfilled.get('Содержание работ (этапы)') ?? 0) + 1)
          continue
        }
        for (const f of schema?.fields ?? []) {
          if (!isFilled(block.content[f.key])) {
            unfilled.set(f.label, (unfilled.get(f.label) ?? 0) + 1)
          }
        }
      }
    }
    return {
      top_services: [...serviceCount.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count).slice(0, 6),
      top_contractors: [...contractorCount.entries()]
        .map(([name, count]) => ({ name, count, rating: db.companies.find((c) => c.name === name)?.rating ?? 0 }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5),
      unfilled_fields: [...unfilled.entries()].map(([field, count]) => ({ field, count })).sort((a, b) => b.count - a.count).slice(0, 6),
      unrecognized_queries: ['требуется помощь с отчетом', 'срочно посчитать', 'не знаю какой продукт нужен'],
    }
  },

  async ingest(file: File): Promise<{ inserted: number; updated: number }> {
    await delay(900)
    return {
      inserted: 2 + (file.size % 7),
      updated: file.size % 3,
    }
  },
  rebuildEmbeddings(): Job {
    return runJob('embeddings_rebuild', () => ({ entities: 148, dim: 768 }), 2400)
  },
}
