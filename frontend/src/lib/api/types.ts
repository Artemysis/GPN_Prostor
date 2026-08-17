export type Role = 'customer' | 'admin'
export type RequestStatus = 'draft' | 'in_progress' | 'ready' | 'submitted' | 'archived'
export type FilledBy = 'manual' | 'ai' | 'mixed'

export interface User {
  id: string
  username: string
  full_name: string
  role: Role
}

export interface Company {
  company_id: string
  name: string
  info: string
  services: string
  rating: number
}

export interface Contract {
  contract_id: string
  contract_number: string
  company_id: string
}

export interface Product {
  product_id: string
  product_name: string
}

export interface ProductRate {
  price_id: string
  product_id: string
  price_name: string
  measurement_name: string
  measurement_type: string
}

export interface ProductOperation {
  operation_id: string
  product_id: string
  operation_name: string
  operation_order: number
}

export interface CostCalculation {
  calc_id: string
  contract_id: string
  calc_name: string
  calc_start_date: string
  calc_end_date: string
  product_id: string
}

export interface CalculationStage {
  stage_id: string
  calc_id: string
  parent_stage_id: string | null
  stage_name: string
  stage_order_num: number
  stage_start_date: string
  stage_end_date: string
  stage_documentation_list: string
}

export interface TzBlockField {
  key: string
  type: 'text' | 'date' | 'list' | 'textarea'
  label: string
  required?: boolean
  placeholder?: string
}

export interface TzTemplateBlockSchema {
  code: string
  name: string
  order: number
  multiple?: boolean
  is_stages_block?: boolean
  fields?: TzBlockField[]
}

export interface TzTemplateStageSkeleton {
  stage_order: number
  stage_name: string
  default_requirements: string
  default_results: string
}

export interface TzTemplate {
  id: string
  code: string
  name: string
  description: string
  blocks_schema: { blocks: TzTemplateBlockSchema[] }
  stages: TzTemplateStageSkeleton[]
}

export interface TzTemplateSummary {
  id: string
  code: string
  name: string
  description: string
}

export interface RequestRecord {
  id: string
  number: string
  user_id: string
  status: RequestStatus
  company_id: string | null
  contract_id: string | null
  product_id: string | null
  title: string
  description: string
  cost_total: number | null
  currency: string
  date_start: string | null
  date_end: string | null
  chat_session_id: string | null
  filled_by: Record<string, FilledBy>
  created_at: string
  updated_at: string
}

export interface TzStage {
  id: string
  stage_order: number
  stage_name: string
  requirements: string
  expected_results: string
  description: string
  stage_start_date: string | null
  stage_end_date: string | null
  filled_by: FilledBy
}

export interface TzBlock {
  block_code: string
  block_name: string
  content: Record<string, unknown>
  filled_by: FilledBy
  is_complete: boolean
  completeness_pct: number
}

export interface RequestTz {
  tz_id: string
  request_id: string
  template_id: string
  version: number
  completeness_pct: number
  blocks: TzBlock[]
  stages: TzStage[]
}

export type ChatRole = 'user' | 'assistant' | 'system'

export interface ChatAction {
  type: 'set_field' | 'suggest_template'
  field?: string
  value?: string
  template_id?: string
  code?: string
  confidence: number
  justification?: string
  applied?: boolean
}

export interface SuggestedProduct {
  product_id: string
  product_name: string
  justification: string
}

export interface SuggestedContractor {
  company_id: string
  name: string
  rating: number
  justification: string
}

export interface SimilarRequest {
  request_id: string
  title: string
  similarity: number
  status: RequestStatus
}

export interface ChatSuggestions {
  products?: SuggestedProduct[]
  contractors?: SuggestedContractor[]
  similar_requests?: SimilarRequest[]
}

export interface ChatMessage {
  id: string
  session_id?: string
  role: ChatRole
  content: string
  actions: ChatAction[] | null
  suggestions: ChatSuggestions | null
  created_at: string
}

export interface ChatSession {
  id: string
  request_id: string | null
  title: string
  created_at: string
}

export type ChatEvent =
  | { type: 'delta'; content: string }
  | { type: 'products'; items: SuggestedProduct[] }
  | { type: 'contractors'; items: SuggestedContractor[] }
  | { type: 'similar_requests'; items: SimilarRequest[] }
  | { type: 'actions'; actions: ChatAction[] }
  | { type: 'done' }

export interface Risk {
  severity: 'high' | 'medium' | 'low'
  category: string
  title: string
  description: string
  suggestion: string
  block_code: string
}

export interface Recommendation {
  title: string
  description: string
  priority: number
  block_code: string
}

export interface TzAnalysis {
  completeness_pct: number
  risks: Risk[]
  recommendations: Recommendation[]
  block_completeness: Record<string, number>
  analyzed_at: string
}

export type DocumentKind = 'tz_final' | 'analytical_report' | 'attachment' | 'kp' | 'rs'

export interface DocumentRecord {
  id: string
  request_id: string
  kind: DocumentKind
  filename: string
  mime_type: string
  size_bytes: number
  generated_by_ai: boolean
  created_at: string
  data_base64?: string
}

export type JobType = 'analyze' | 'export' | 'fill_ai' | 'embeddings_rebuild'
export type JobStatus = 'pending' | 'running' | 'done' | 'failed'

export interface Job {
  id: string
  type: JobType
  status: JobStatus
  result: unknown
  error: string | null
}

export interface AppliedDiff {
  field: string
  old: string
  new: string
}

export interface RequestInput {
  title?: string
  description?: string
  company_id?: string | null
  contract_id?: string | null
  product_id?: string | null
  cost_total?: number | null
  date_start?: string | null
  date_end?: string | null
}

export interface AnalyticsTz {
  total_tz: number
  avg_completeness: number
  by_type: { type: string; count: number }[]
  by_stage_popularity: { stage: string; count: number }[]
  typical_errors: { title: string; count: number }[]
}

export interface AnalyticsSearch {
  top_services: { name: string; count: number }[]
  top_contractors: { name: string; count: number; rating: number }[]
  unfilled_fields: { field: string; count: number }[]
  unrecognized_queries: string[]
}
