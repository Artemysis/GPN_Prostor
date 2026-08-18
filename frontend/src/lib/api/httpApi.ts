import { http, API_URL } from './client'
import type {
  AnalyticsSearch,
  AnalyticsTz,
  ApplyResult,
  CalculationStage,
  ChatAction,
  ChatEvent,
  ChatMessage,
  ChatSession,
  Company,
  Contract,
  CostCalculation,
  DocumentKind,
  DocumentRecord,
  FilledBy,
  Job,
  Product,
  ProductOperation,
  ProductRate,
  RequestDetail,
  RequestRecord,
  RequestTz,
  TzAnalysis,
  TzStage,
  TzTemplate,
  TzTemplateSummary,
  User,
} from './types'

function unwrapApiError(error: unknown): never {
  const err = error as { response?: { data?: { error?: { message?: string } } }; message?: string }
  const message = err.response?.data?.error?.message ?? err.message ?? 'Ошибка запроса к серверу'
  throw new Error(message)
}

async function req<T>(fn: () => Promise<{ data: T }>): Promise<T> {
  try {
    const res = await fn()
    return res.data
  } catch (error) {
    unwrapApiError(error)
  }
}

// --- Auth --------------------------------------------------------------

export async function login(username: string): Promise<{ access_token: string; user: User }> {
  const data = await req<{ access_token: string; user: { id: string; username: string; role: User['role'] } }>(() =>
    http.post('/auth/login', { username }),
  )
  return { access_token: data.access_token, user: { ...data.user, full_name: data.user.username } }
}

// --- Справочники ---------------------------------------------------------

export function listCompanies(search?: string): Promise<Company[]> {
  return req(() => http.get('/companies', { params: { search } }))
}
export function getCompany(id: string) {
  return req<Company & { contracts: Contract[] }>(() => http.get(`/companies/${id}`))
}
export function listContracts(companyId?: string): Promise<Contract[]> {
  return req(() => http.get('/contracts', { params: { company_id: companyId } }))
}
export function listProducts(contractId?: string): Promise<Product[]> {
  return req(() => http.get('/products', { params: { contract_id: contractId } }))
}
export function getProductRates(productId: string): Promise<ProductRate[]> {
  return req(() => http.get(`/products/${productId}/rates`))
}
export function getProductOperations(productId: string): Promise<ProductOperation[]> {
  return req(() => http.get(`/products/${productId}/operations`))
}
export function listCalculations(contractId?: string): Promise<CostCalculation[]> {
  return req(() => http.get('/cost-calculations', { params: { contract_id: contractId } }))
}
export function listCalculationStages(calcId: string): Promise<CalculationStage[]> {
  return req(() => http.get(`/cost-calculations/${calcId}/stages`))
}

// --- Шаблоны ТЗ -----------------------------------------------------------

export function listTemplates(): Promise<TzTemplateSummary[]> {
  return req(() => http.get('/tz-templates'))
}
export function getTemplate(id: string): Promise<TzTemplate> {
  return req(() => http.get(`/tz-templates/${id}`))
}
export function recommendTemplate(prompt: string, requestContext?: Record<string, unknown>) {
  return req(() => http.post('/tz-templates/recommend', { prompt, request_context: requestContext }))
}

// --- Заявки ----------------------------------------------------------------

export function createRequest(input: {
  title?: string
  description?: string
  company_id?: string | null
  contract_id?: string | null
  product_id?: string | null
  cost_total?: number | null
  date_start?: string | null
  date_end?: string | null
}): Promise<RequestRecord> {
  return req(() => http.post('/requests', input))
}
export async function listRequests(status?: string): Promise<RequestRecord[]> {
  const data = await req<{ items: RequestRecord[]; total: number }>(() => http.get('/requests', { params: { status } }))
  return data.items
}
export function getRequest(id: string): Promise<RequestDetail> {
  return req(() => http.get(`/requests/${id}`))
}
export function updateRequest(id: string, patch: Record<string, unknown>): Promise<RequestRecord> {
  return req(() => http.patch(`/requests/${id}`, patch))
}
export function deleteRequest(id: string): Promise<void> {
  return req(() => http.delete(`/requests/${id}`))
}
export function submitRequest(id: string): Promise<RequestRecord> {
  return req(() => http.post(`/requests/${id}/submit`))
}

// --- Конструктор ТЗ ---------------------------------------------------------

export async function createTz(requestId: string, templateId: string, prefill = false): Promise<RequestTz> {
  try {
    return await req(() => http.post(`/requests/${requestId}/tz`, { template_id: templateId, prefill_from_chat: prefill }))
  } catch (error) {
    // ТЗ уже создано (409) — возвращаем существующее, чтобы вызов был идемпотентным
    const existing = await getTz(requestId)
    if (existing) return existing
    throw error
  }
}
export async function getTz(requestId: string): Promise<RequestTz | null> {
  try {
    return await req<RequestTz>(() => http.get(`/requests/${requestId}/tz`))
  } catch {
    return null
  }
}
export function saveBlock(requestId: string, blockCode: string, content: Record<string, unknown>, filledBy: FilledBy) {
  return req(() => http.patch(`/requests/${requestId}/tz/blocks/${blockCode}`, { content, filled_by: filledBy }))
}
export function addStage(requestId: string, stage: Partial<TzStage> & { stage_name: string }): Promise<TzStage> {
  return req(() =>
    http.post(`/requests/${requestId}/tz/stages`, {
      stage_order: stage.stage_order ?? 1,
      stage_name: stage.stage_name,
      requirements: stage.requirements ?? '',
      expected_results: stage.expected_results ?? '',
      description: stage.description ?? '',
      stage_start_date: stage.stage_start_date ?? null,
      stage_end_date: stage.stage_end_date ?? null,
    }),
  )
}
export function updateStage(requestId: string, stageId: string, patch: Partial<TzStage>): Promise<TzStage> {
  return req(() => http.patch(`/requests/${requestId}/tz/stages/${stageId}`, patch))
}
export function deleteStage(requestId: string, stageId: string): Promise<void> {
  return req(() => http.delete(`/requests/${requestId}/tz/stages/${stageId}`))
}

// --- ИИ-заполнение и анализ --------------------------------------------------

export function startFillAi(requestId: string, blockCode: string, hint?: string): Promise<Job> {
  return req<{ job_id: string }>(() => http.post(`/requests/${requestId}/tz/blocks/${blockCode}/fill-ai`, { hint })).then(
    (d) => ({ id: d.job_id, type: 'fill_ai', status: 'pending', result: null, error: null }),
  )
}
export function startAnalyze(requestId: string): Promise<Job> {
  return req<{ job_id: string }>(() => http.post(`/requests/${requestId}/tz/analyze`)).then((d) => ({
    id: d.job_id,
    type: 'analyze',
    status: 'pending',
    result: null,
    error: null,
  }))
}
export async function getAnalysis(requestId: string): Promise<TzAnalysis | null> {
  try {
    return await req<TzAnalysis>(() => http.get(`/requests/${requestId}/tz/analysis`))
  } catch {
    return null
  }
}
export function getCompleteness(requestId: string) {
  return req<{ completeness_pct: number; block_completeness: Record<string, number> }>(() =>
    http.get(`/requests/${requestId}/tz/completeness`),
  )
}

// --- Чат ---------------------------------------------------------------------

export async function createChatSession(requestId: string): Promise<ChatSession> {
  const data = await req<{ session_id: string }>(() => http.post('/chat/sessions', { request_id: requestId }))
  return { id: data.session_id, request_id: requestId }
}
export async function getChatMessages(sessionId: string): Promise<ChatMessage[]> {
  const data = await req<{ id: string; role: ChatMessage['role']; content: string; actions: ChatAction[] | null; created_at: string }[]>(
    () => http.get(`/chat/sessions/${sessionId}/messages`),
  )
  return data.map((m) => ({ ...m, session_id: sessionId, suggestions: null }))
}

export async function streamChat(sessionId: string, content: string, onEvent: (e: ChatEvent) => void): Promise<void> {
  const token = localStorage.getItem('prostor.token')
  const response = await fetch(`${API_URL}/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content, stream: true }),
  })
  if (!response.ok || !response.body) {
    throw new Error(`Чат недоступен (HTTP ${response.status})`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      const payload = line.slice(5).trim()
      if (payload === '[DONE]') {
        onEvent({ type: 'done' })
        continue
      }
      try {
        const parsed = JSON.parse(payload) as ChatEvent
        onEvent(parsed)
      } catch {
        // игнорируем некорректные фрагменты потока
      }
    }
  }
}

export async function applyActions(sessionId: string, actions: ChatAction[]): Promise<ApplyResult> {
  return req<ApplyResult>(() => http.post(`/chat/sessions/${sessionId}/apply`, { actions }))
}

// --- Документы / выгрузка ----------------------------------------------------

export function startExport(
  requestId: string,
  formats: string[],
  includeAnalyticalReport: boolean,
  includePackage = true,
): Promise<Job> {
  return req<{ job_id: string }>(() =>
    http.post(`/requests/${requestId}/export`, {
      formats,
      include_analytical_report: includeAnalyticalReport,
      include_package: includePackage,
    }),
  ).then((d) => ({ id: d.job_id, type: 'export', status: 'pending', result: null, error: null }))
}
export function listDocuments(requestId: string): Promise<DocumentRecord[]> {
  return req(() => http.get(`/requests/${requestId}/documents`))
}
export function downloadDocument(docId: string): void {
  window.open(`${API_URL}/documents/${docId}/download`, '_blank')
}
export function uploadAttachment(requestId: string, file: File, kind: DocumentKind = 'attachment'): Promise<DocumentRecord> {
  const form = new FormData()
  form.append('kind', kind)
  form.append('file', file)
  return req(() => http.post(`/requests/${requestId}/attachments`, form, { headers: { 'Content-Type': 'multipart/form-data' } }))
}
export function deleteAttachment(requestId: string, docId: string): Promise<void> {
  return req(() => http.delete(`/requests/${requestId}/attachments/${docId}`))
}

// --- Фоновые задачи ----------------------------------------------------------

export function getJob(id: string): Promise<Job> {
  return req(() => http.get(`/jobs/${id}`))
}

// --- Аналитика -----------------------------------------------------------

export function getAnalyticsTz(): Promise<AnalyticsTz> {
  return req(() => http.get('/analytics/tz'))
}
export function getAnalyticsSearch(): Promise<AnalyticsSearch> {
  return req(() => http.get('/analytics/search'))
}

// --- Админ / ингест -----------------------------------------------------------

export function ingestCompanies(file: File) {
  const form = new FormData()
  form.append('file', file)
  return req<{ inserted: number; updated: number }>(() => http.post('/admin/ingest/companies', form))
}
export function ingestContracts(file: File) {
  const form = new FormData()
  form.append('file', file)
  return req<{ inserted: number; updated: number }>(() => http.post('/admin/ingest/contracts', form))
}
export function ingestProductsRates(productsFile: File, ratesFile?: File) {
  const form = new FormData()
  form.append('products_file', productsFile)
  if (ratesFile) form.append('rates_file', ratesFile)
  return req<{ inserted: number; updated: number }>(() => http.post('/admin/ingest/products-rates', form))
}
export function ingestOperations(file: File) {
  const form = new FormData()
  form.append('file', file)
  return req<{ inserted: number; updated: number }>(() => http.post('/admin/ingest/operations', form))
}
export function ingestCalculations(file: File) {
  const form = new FormData()
  form.append('file', file)
  return req<{ inserted: number; updated: number }>(() => http.post('/admin/ingest/calculations', form))
}
export function rebuildEmbeddings(): Promise<Job> {
  return req<{ job_id: string }>(() => http.post('/admin/embeddings/rebuild', {})).then((d) => ({
    id: d.job_id,
    type: 'embeddings_rebuild',
    status: 'pending',
    result: null,
    error: null,
  }))
}
