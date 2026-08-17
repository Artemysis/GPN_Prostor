import { uid } from '@/lib/utils'
import { computeBlockPct, computeTzPct, draftBlockContent, draftStages } from './drafts'
import type {
  CalculationStage,
  ChatMessage,
  ChatSession,
  Company,
  Contract,
  CostCalculation,
  DocumentRecord,
  Job,
  Product,
  ProductOperation,
  ProductRate,
  RequestRecord,
  RequestTz,
  TzAnalysis,
  TzBlock,
  TzStage,
  TzTemplate,
  TzTemplateBlockSchema,
  User,
  FilledBy,
} from './types'

export interface Db {
  users: User[]
  companies: Company[]
  contracts: Contract[]
  products: Product[]
  contract_products: { contract_id: string; product_id: string }[]
  product_rates: ProductRate[]
  product_operations: ProductOperation[]
  cost_calculations: CostCalculation[]
  calculation_stages: CalculationStage[]
  templates: TzTemplate[]
  requests: RequestRecord[]
  tzs: RequestTz[]
  analyses: (TzAnalysis & { tz_id: string })[]
  documents: DocumentRecord[]
  chat_sessions: ChatSession[]
  chat_messages: ChatMessage[]
  jobs: Job[]
  counters: { request: number }
}

const baseBlocks = (): TzTemplateBlockSchema[] => [
  {
    code: 'goals',
    name: 'Цели и задачи работ',
    order: 1,
    multiple: true,
    fields: [
      { key: 'goal_text', type: 'textarea', label: 'Цель', required: true },
      { key: 'tasks', type: 'list', label: 'Задачи', required: true },
    ],
  },
  {
    code: 'scope',
    name: 'Периметр работ',
    order: 2,
    fields: [
      { key: 'location', type: 'text', label: 'Место оказания' },
      { key: 'field_name', type: 'text', label: 'Наименование месторождения', required: true, placeholder: '{Наименование-Месторождения}' },
    ],
  },
  {
    code: 'terms',
    name: 'Сроки выполнения работ',
    order: 3,
    fields: [
      { key: 'date_start', type: 'date', label: 'Начало', required: true },
      { key: 'date_end', type: 'date', label: 'Окончание', required: true },
    ],
  },
  { code: 'work_content', name: 'Содержание работ', order: 4, is_stages_block: true },
  {
    code: 'conditions',
    name: 'Условия выполнения работы',
    order: 5,
    fields: [
      { key: 'source_data', type: 'textarea', label: 'Исходная информация от Заказчика', required: true },
      { key: 'software', type: 'text', label: 'Программное обеспечение' },
    ],
  },
  {
    code: 'documentation',
    name: 'Требования к документации',
    order: 6,
    fields: [{ key: 'report_formats', type: 'text', label: 'Форматы отчетов', required: true }],
  },
  {
    code: 'quality_control',
    name: 'Контроль качества',
    order: 7,
    fields: [{ key: 'acceptance', type: 'textarea', label: 'Условия приемки', required: true }],
  },
  {
    code: 'signatures',
    name: 'Подписи сторон',
    order: 8,
    fields: [
      { key: 'customer_signee', type: 'text', label: 'Подписант Заказчика' },
      { key: 'contractor_signee', type: 'text', label: 'Подписант Исполнителя' },
    ],
  },
]

function template(
  id: string,
  code: string,
  name: string,
  description: string,
  stages: [string, string, string][],
): TzTemplate {
  return {
    id,
    code,
    name,
    description,
    blocks_schema: { blocks: baseBlocks() },
    stages: stages.map(([stage_name, default_requirements, default_results], i) => ({
      stage_order: i + 1,
      stage_name,
      default_requirements,
      default_results,
    })),
  }
}

function mkTz(requestId: string, tpl: TzTemplate, filledCodes: string[], filledBy: FilledBy): RequestTz {
  const ctx = { field_name: 'Ваньгаяхинское', template_name: tpl.name }
  let tzStages: TzStage[] = []
  const blocks: TzBlock[] = tpl.blocks_schema.blocks.map((b) => {
    const filled = filledCodes.includes(b.code)
    if (b.is_stages_block) {
      if (filled) tzStages = draftStages(tpl.stages, filledBy)
      return {
        block_code: b.code,
        block_name: b.name,
        content: {},
        filled_by: filled ? filledBy : 'manual',
        is_complete: false,
        completeness_pct: computeBlockPct(undefined, {}, true, tzStages),
      }
    }
    const content = filled ? draftBlockContent(b.code, ctx) : {}
    return {
      block_code: b.code,
      block_name: b.name,
      content,
      filled_by: filled ? filledBy : 'manual',
      is_complete: false,
      completeness_pct: computeBlockPct(b.fields, content),
    }
  })
  return {
    tz_id: uid('tz_'),
    request_id: requestId,
    template_id: tpl.id,
    version: 1,
    completeness_pct: computeTzPct(blocks),
    blocks,
    stages: tzStages,
  }
}

export function seedDb(): Db {
  const users: User[] = [
    { id: 'u_demo', username: 'demo', full_name: 'Демо Пользователь', role: 'customer' },
    { id: 'u_admin', username: 'admin', full_name: 'Администратор', role: 'admin' },
  ]

  const companies: Company[] = [
    {
      company_id: 'c_nng',
      name: 'АО «ННГ»',
      info: 'Научно-инженерный центр, специализируется на геологическом моделировании и подсчете запасов',
      services: 'Геология и геомоделирование, подсчет запасов, петрофизика, ГТИ, сейсмогеология',
      rating: 5,
    },
    {
      company_id: 'c_tnnc',
      name: 'ООО «Тюменский нефтяной исследовательский центр»',
      info: 'Сопровождение строительства скважин, технологические решения по бурению и заканчиванию',
      services: 'Сопровождение бурения, ПТД, заканчивание скважин, геомеханика, fluids',
      rating: 4,
    },
    {
      company_id: 'c_ntc',
      name: 'НТЦ ПАО «Газпром нефть»',
      info: 'Корпоративный научно-технический центр: концепты разработки, проектные документы',
      services: 'Концепты разработки, ПЗ новых месторождений, авторский надзор, НИОКР',
      rating: 5,
    },
    {
      company_id: 'c_ural',
      name: 'ООО «УралНефтеПроект»',
      info: 'Проектирование объектов обустройства и инфраструктуры месторождений',
      services: 'Концепт обустройства, наружные сети, трубопроводы, ТЭО',
      rating: 4,
    },
    {
      company_id: 'c_sibnk',
      name: 'ООО «СибНефтеГеофизика»',
      info: 'Полевые сейсморазведочные работы и обработка данных 2D/3D',
      services: 'Сейсморазведка 2D/3D, обработка и интерпретация, ПДИ',
      rating: 3,
    },
  ]

  const contracts: Contract[] = [
    { contract_id: 'k_001', contract_number: '001-ГНЗ-НТЦ-Д/ГНЗ', company_id: 'c_nng' },
    { contract_id: 'k_002', contract_number: '002-ГНЗ-НТЦ-Д/ГНЗ', company_id: 'c_nng' },
    { contract_id: 'k_017', contract_number: '17-23-ТНИЦ/НГДУ', company_id: 'c_tnnc' },
    { contract_id: 'k_024', contract_number: '24-31-УНП/ПР', company_id: 'c_ural' },
    { contract_id: 'k_008', contract_number: '08-15-СНГ/СБ', company_id: 'c_sibnk' },
    { contract_id: 'k_005', contract_number: '05-24-НТЦ/КР', company_id: 'c_ntc' },
  ]

  const products: Product[] = [
    { product_id: 'p_reserves', product_name: 'Подсчет запасов' },
    { product_id: 'p_geology', product_name: 'Концепт геологии' },
    { product_id: 'p_facilities', product_name: 'Концепт обустройства' },
    { product_id: 'p_completion', product_name: 'Интегрированный концепт заканчивания' },
    { product_id: 'p_development', product_name: 'Интегрированный концепт развития' },
    { product_id: 'p_engineering', product_name: 'Сопровождение инженерных работ и высокорисковых операций' },
    { product_id: 'p_ptd_nng', product_name: 'ПТД ННГ' },
    { product_id: 'p_ptd_do', product_name: 'ПТД ДО' },
    { product_id: 'p_pz', product_name: 'ПЗ Нового месторождения' },
  ]

  const contract_products = [
    { contract_id: 'k_001', product_id: 'p_geology' },
    { contract_id: 'k_001', product_id: 'p_reserves' },
    { contract_id: 'k_002', product_id: 'p_reserves' },
    { contract_id: 'k_017', product_id: 'p_ptd_nng' },
    { contract_id: 'k_017', product_id: 'p_completion' },
    { contract_id: 'k_017', product_id: 'p_engineering' },
    { contract_id: 'k_024', product_id: 'p_facilities' },
    { contract_id: 'k_008', product_id: 'p_development' },
    { contract_id: 'k_005', product_id: 'p_pz' },
    { contract_id: 'k_005', product_id: 'p_geology' },
  ]

  const product_rates: ProductRate[] = [
    { price_id: 'r_1', product_id: 'p_geology', price_name: 'Ведущий геолог', measurement_name: 'Человеко-часы', measurement_type: 'LaborUnit' },
    { price_id: 'r_2', product_id: 'p_geology', price_name: 'Геолог I категории', measurement_name: 'Человеко-часы', measurement_type: 'LaborUnit' },
    { price_id: 'r_3', product_id: 'p_geology', price_name: 'Бурение и ВСР L2', measurement_name: 'Человеко-дни', measurement_type: 'LaborUnit' },
    { price_id: 'r_4', product_id: 'p_completion', price_name: 'Инженер по заканчиванию', measurement_name: 'Человеко-часы', measurement_type: 'LaborUnit' },
    { price_id: 'r_5', product_id: 'p_ptd_nng', price_name: 'Технолог по бурению', measurement_name: 'Человеко-часы', measurement_type: 'LaborUnit' },
  ]

  const product_operations: ProductOperation[] = [
    { operation_id: 'o_1', product_id: 'p_geology', operation_name: 'Формирование и анализ базы данных', operation_order: 1 },
    { operation_id: 'o_2', product_id: 'p_geology', operation_name: 'Петрофизические исследования', operation_order: 2 },
    { operation_id: 'o_3', product_id: 'p_geology', operation_name: 'Построение 3D геологической модели', operation_order: 3 },
    { operation_id: 'o_4', product_id: 'p_geology', operation_name: 'Подсчет запасов', operation_order: 4 },
    { operation_id: 'o_5', product_id: 'p_completion', operation_name: 'Проектирование заканчивания скважин', operation_order: 1 },
    { operation_id: 'o_6', product_id: 'p_completion', operation_name: 'Подбор технологических жидкостей и жидкостей глушения', operation_order: 2 },
  ]

  const cost_calculations: CostCalculation[] = [
    { calc_id: 'cc_1', contract_id: 'k_001', calc_name: 'РС Концепт геологии Ваньгаяхинское', calc_start_date: '2026-01-12', calc_end_date: '2026-12-25', product_id: 'p_geology' },
    { calc_id: 'cc_2', contract_id: 'k_017', calc_name: 'РС ПТД БНГ 2026', calc_start_date: '2026-03-01', calc_end_date: '2026-11-30', product_id: 'p_ptd_nng' },
  ]

  const calculation_stages: CalculationStage[] = [
    { stage_id: 'cs_1', calc_id: 'cc_1', parent_stage_id: null, stage_name: 'Этап 1. Формирование базы данных', stage_order_num: 1, stage_start_date: '2026-01-12', stage_end_date: '2026-03-31', stage_documentation_list: 'Информационный отчет' },
    { stage_id: 'cs_2', calc_id: 'cc_1', parent_stage_id: null, stage_name: 'Этап 2. Петрофизические исследования', stage_order_num: 2, stage_start_date: '2026-04-01', stage_end_date: '2026-06-30', stage_documentation_list: 'Отчет по петрофизике' },
    { stage_id: 'cs_3', calc_id: 'cc_1', parent_stage_id: null, stage_name: 'Этап 3. 3D геомоделирование', stage_order_num: 3, stage_start_date: '2026-07-01', stage_end_date: '2026-10-31', stage_documentation_list: '3D модель, отчет' },
    { stage_id: 'cs_4', calc_id: 'cc_1', parent_stage_id: null, stage_name: 'Этап 4. Подсчет запасов', stage_order_num: 4, stage_start_date: '2026-11-01', stage_end_date: '2026-12-25', stage_documentation_list: 'Отчет по подсчету запасов' },
  ]

  const templates: TzTemplate[] = [
    template('t_geo', 'concept_geology', 'ТЗ Концепт геологии', 'Геологическое изучение, подсчет запасов, 3D геомоделирование', [
      ['Этап 1. Формирование базы данных, проверка, объединение и анализ исходной информации', 'Учет всей актуальной геолого-промысловой информации', 'Формирование рабочих баз данных в ПО'],
      ['Этап 2. Петрофизические исследования керна и ГИС', 'Стандартизация и увязка данных ГИС, петрофизические зависимости', 'Петрофизическая основа модели'],
      ['Этап 3. Построение 3D геологической модели', 'Учет структурных построений, литологии и ФЕС', '3D геологическая модель месторождения'],
      ['Этап 4. Подсчет запасов и подготовка отчетности', 'Категоризация запасов, подсчетные параметры', 'Отчет по подсчету запасов'],
    ]),
    template('t_fac', 'concept_facilities', 'ТЗ Концепт обустройства', 'Варианты обустройства, инфраструктура, ТЭО', [
      ['Этап 1. Анализ исходных данных и технологических нагрузок', 'Сбор и верификация промысловых данных', 'Технологические нагрузки'],
      ['Этап 2. Разработка вариантов обустройства', 'Многоварантное проектирование инфраструктуры', 'Матрица вариантов обустройства'],
      ['Этап 3. Технико-экономическая оценка вариантов', 'CAPEX/OPEX по вариантам', 'ТЭО выбранного варианта'],
    ]),
    template('t_comp', 'concept_completion', 'ТЗ Интегрированный концепт заканчивания', 'Заканчивание скважин, дизайн, жидкости, ГТИ', [
      ['Этап 1. Анализ опыта заканчивания и геомеханика', 'Обоснование устойчивости ствола', 'Геомеханическая модель'],
      ['Этап 2. Проектирование заканчивания', 'Конструкции забоев, перфорация, крепление', 'Дизайны заканчивания'],
      ['Этап 3. Подбор технологических жидкостей', 'Совместимость с коллектором', 'Программы жидкостей'],
      ['Этап 4. Анализ результатов и сопровождение', 'Сопровождение реализации', 'Итоговый отчет'],
    ]),
    template('t_dev', 'concept_development', 'ТЗ Интегрированный концепт развития', 'Оптимизация разработки, бурения и добычи', [
      ['Этап 1. Анализ текущего состояния разработки', 'История разработки, интерференция', 'Анализ выработки запасов'],
      ['Этап 2. Гидродинамическое моделирование', 'Калибровка секторных моделей', 'ГДМ сценариев'],
      ['Этап 3. Рекомендации по развитию', 'Программа бурения и МУН', 'Оптимальный сценарий разработки'],
    ]),
    template('t_eng', 'engineering_support', 'ТЗ Сопровождение инженерных работ и высокорисковых операций', 'Инженерное сопровождение строительства скважин', [
      ['Этап 1. Подготовка программы работ', 'Анализ рисков операции', 'Программа работ'],
      ['Этап 2. Онлайн-сопровождение операции', 'Мониторинг параметров, консультации', 'Суточные отчеты'],
      ['Этап 3. Разбор результатов', 'Анализ фактических параметров', 'Итоговый отчет с рекомендациями'],
    ]),
    template('t_ptd_nng', 'ptd_nng', 'Приложение 1. ТЗ (шаблон ПТД ННГ)_2026', 'Проектно-технологическая документация ННГ', [
      ['Этап 1. Анализ геолого-технической информации', 'Сбор данных по кустам', 'ГТНИ'],
      ['Этап 2. Разработка ПТД', 'Конструкции скважин, решения по бурению', 'Пакет ПТД'],
      ['Этап 3. Согласование и корректировка', 'Замечания Заказчика', 'Согласованная ПТД'],
    ]),
    template('t_ptd_do', 'ptd_do', 'Приложение 1. ТЗ (шаблон ПТД ДО)_2026', 'Проектно-технологическая документация ДО', [
      ['Этап 1. Анализ исходных данных', 'Данные по эксплуатационному фонду', 'Аналитическая справка'],
      ['Этап 2. Разработка ПТД', 'Решения по ремонту и оптимизации', 'Пакет ПТД'],
      ['Этап 3. Согласование', 'Замечания Заказчика', 'Согласованная ПТД'],
    ]),
    template('t_pz', 'pz_new', 'Приложение 1. ТЗ (ПЗ Нового м-я)', 'Поисковые и оценочные работы нового месторождения', [
      ['Этап 1. Обобщение геолого-геофизической информации', 'Комплексирование данных 2D/3D', 'Структурные построения'],
      ['Этап 2. Выбор объектов и параметров бурения', 'Обоснование поисковых объектов', 'Программа поискового бурения'],
      ['Этап 3. Оценка ресурсов', 'Параметры для подсчета ресурсов', 'Оценка ресурсов'],
      ['Этап 4. Подготовка проектного документа', 'Требования НМД', 'Проектный документ'],
    ]),
    template('t_form21', 'form_2_1', 'Приложение № 2.1 Форма Технического задания', 'Универсальная форма ТЗ', [
      ['Этап 1. Подготовительные работы', 'Согласование периметра', 'План работ'],
      ['Этап 2. Основные работы', 'Согласно техническому заданию', 'Результаты работ'],
      ['Этап 3. Отчетность', 'Формирование итоговых документов', 'Итоговый отчет'],
    ]),
  ]

  const requests: RequestRecord[] = [
    {
      id: 'r_0001',
      number: 'REQ-2026-0001',
      user_id: 'u_demo',
      status: 'submitted',
      company_id: 'c_nng',
      contract_id: 'k_001',
      product_id: 'p_geology',
      title: 'Подсчет запасов и 3D геомодель, Ваньгаяхинское месторождение',
      description: 'Актуализация запасов по объекту и построение 3D геологической модели',
      cost_total: 24500000,
      currency: 'RUB',
      date_start: '2026-01-12',
      date_end: '2026-12-25',
      chat_session_id: 's_0001',
      filled_by: { company_id: 'ai', product_id: 'ai' },
      created_at: '2026-06-03T09:12:00Z',
      updated_at: '2026-07-14T15:40:00Z',
    },
    {
      id: 'r_0002',
      number: 'REQ-2026-0002',
      user_id: 'u_demo',
      status: 'submitted',
      company_id: 'c_ural',
      contract_id: 'k_024',
      product_id: 'p_facilities',
      title: 'Концепт обустройства Восточно-Полуденного лицензионного участка',
      description: 'Разработка вариантов обустройства с ТЭО',
      cost_total: 18700000,
      currency: 'RUB',
      date_start: '2026-02-01',
      date_end: '2026-10-30',
      chat_session_id: null,
      filled_by: {},
      created_at: '2026-06-20T11:05:00Z',
      updated_at: '2026-07-30T10:00:00Z',
    },
    {
      id: 'r_0003',
      number: 'REQ-2026-0003',
      user_id: 'u_demo',
      status: 'ready',
      company_id: 'c_tnnc',
      contract_id: 'k_017',
      product_id: 'p_completion',
      title: 'ИК заканчивания скважин, Хыльчуюское месторождение',
      description: 'Интегрированный концепт заканчивания с геомеханикой',
      cost_total: 31200000,
      currency: 'RUB',
      date_start: '2026-03-01',
      date_end: '2027-02-28',
      chat_session_id: null,
      filled_by: { cost_total: 'ai' },
      created_at: '2026-07-02T08:44:00Z',
      updated_at: '2026-08-05T13:26:00Z',
    },
    {
      id: 'r_0004',
      number: 'REQ-2026-0004',
      user_id: 'u_demo',
      status: 'in_progress',
      company_id: 'c_tnnc',
      contract_id: 'k_017',
      product_id: 'p_ptd_nng',
      title: 'ПТД для строительства скважин БНГ, куст 41',
      description: '',
      cost_total: null,
      currency: 'RUB',
      date_start: '2026-08-01',
      date_end: '2026-12-31',
      chat_session_id: null,
      filled_by: {},
      created_at: '2026-07-28T16:20:00Z',
      updated_at: '2026-08-10T09:15:00Z',
    },
    {
      id: 'r_0005',
      number: 'REQ-2026-0005',
      user_id: 'u_demo',
      status: 'draft',
      company_id: 'c_ntc',
      contract_id: 'k_005',
      product_id: 'p_pz',
      title: 'ПЗ нового месторождения (черновик)',
      description: 'Предварительная заявка',
      cost_total: null,
      currency: 'RUB',
      date_start: null,
      date_end: null,
      chat_session_id: null,
      filled_by: {},
      created_at: '2026-08-11T10:00:00Z',
      updated_at: '2026-08-11T10:00:00Z',
    },
    {
      id: 'r_0006',
      number: 'REQ-2026-0006',
      user_id: 'u_demo',
      status: 'submitted',
      company_id: 'c_sibnk',
      contract_id: 'k_008',
      product_id: 'p_development',
      title: 'Сейсморазведка 3D и концепт развития Малоямальского',
      description: '',
      cost_total: 44200000,
      currency: 'RUB',
      date_start: '2026-04-01',
      date_end: '2027-03-31',
      chat_session_id: null,
      filled_by: {},
      created_at: '2026-05-14T12:30:00Z',
      updated_at: '2026-06-01T09:00:00Z',
    },
  ]

  const tplGeo = templates[0]
  const tplFac = templates[1]
  const tplComp = templates[2]
  const tplPtd = templates[5]

  const tz1 = mkTz('r_0001', tplGeo, ['goals', 'scope', 'terms', 'work_content', 'conditions', 'documentation', 'quality_control'], 'mixed')
  const tz2 = mkTz('r_0002', tplFac, ['goals', 'scope', 'terms'], 'manual')
  const tz3 = mkTz('r_0003', tplComp, ['goals', 'scope', 'terms', 'work_content', 'conditions', 'documentation', 'quality_control', 'signatures'], 'manual')
  const tz4 = mkTz('r_0004', tplPtd, ['goals', 'terms'], 'manual')

  const analyses: (TzAnalysis & { tz_id: string })[] = [
    {
      tz_id: tz1.tz_id,
      completeness_pct: 78,
      block_completeness: { goals: 100, scope: 50, terms: 100, work_content: 85, conditions: 60, documentation: 100, quality_control: 100, signatures: 0 },
      risks: [
        { severity: 'high', category: 'missing_data', title: 'Не указан объект работ', description: 'Поле scope.field_name пусто', suggestion: 'Укажите наименование месторождения', block_code: 'scope' },
        { severity: 'high', category: 'logical', title: '3D-модель без этапа подготовки исходных данных', description: 'Указано построение 3D-геомодели, но отсутствует этап формирования базы данных', suggestion: 'Добавить этап 1 «Формирование базы данных»', block_code: 'work_content' },
        { severity: 'medium', category: 'terms', title: 'Заявленный срок ниже типового', description: 'date_end раньше типового срока для этого типа работ (обычно 12 мес.)', suggestion: 'Проверить календарный план', block_code: 'terms' },
      ],
      recommendations: [
        { title: 'Добавить исходные данные', description: 'Перед согласованием необходимо добавить требования к исходным материалам', priority: 1, block_code: 'conditions' },
        { title: 'Указать требования к 3D-модели', description: 'Добавить раздел требований к 3D-модели в work_content', priority: 2, block_code: 'work_content' },
        { title: 'Проверить календарный план', description: 'Срок работ ниже типового', priority: 3, block_code: 'terms' },
      ],
      analyzed_at: '2026-07-14T15:40:00Z',
    },
  ]

  const documents: DocumentRecord[] = [
    { id: 'd_1', request_id: 'r_0001', kind: 'tz_final', filename: 'ТЗ_REQ-2026-0001_Концепт_геологии.docx', mime_type: 'application/msword', size_bytes: 84210, generated_by_ai: false, created_at: '2026-07-14T15:41:00Z' },
    { id: 'd_2', request_id: 'r_0001', kind: 'analytical_report', filename: 'Аналитический_отчет_REQ-2026-0001.docx', mime_type: 'application/msword', size_bytes: 51800, generated_by_ai: true, created_at: '2026-07-14T15:42:00Z' },
    { id: 'd_3', request_id: 'r_0001', kind: 'kp', filename: 'КП_ННГ_24.5МР.pdf', mime_type: 'application/pdf', size_bytes: 1042000, generated_by_ai: false, created_at: '2026-07-01T10:00:00Z' },
  ]

  const chat_sessions: ChatSession[] = [
    { id: 's_0001', request_id: 'r_0001', title: 'Подбор продукта и подрядчика', created_at: '2026-06-03T09:15:00Z' },
  ]

  const chat_messages: ChatMessage[] = [
    {
      id: 'm_1',
      session_id: 's_0001',
      role: 'user',
      content: 'Нужно оценить запасы по объекту и построить 3D-геомодель',
      actions: null,
      suggestions: null,
      created_at: '2026-06-03T09:15:00Z',
    },
    {
      id: 'm_2',
      session_id: 's_0001',
      role: 'assistant',
      content:
        'Классифицировал намерение: подсчет запасов и 3D геомоделирование. Предлагаю продукт «Концепт геологии» и подрядчика АО «ННГ» (рейтинг 5, опыт аналогичных работ). Все предложения ниже — черновики, примените те, что подходят.',
      actions: [
        { type: 'set_field', field: 'company_id', value: 'c_nng', confidence: 0.9, justification: 'Высокий рейтинг и профильные услуги', applied: true },
        { type: 'set_field', field: 'product_id', value: 'p_geology', confidence: 0.92, justification: 'Точное соответствие запросу', applied: true },
        { type: 'suggest_template', template_id: 't_geo', code: 'concept_geology', confidence: 0.9 },
      ],
      suggestions: {
        products: [{ product_id: 'p_geology', product_name: 'Концепт геологии', justification: 'Включает подсчет запасов и построение 3D модели' }],
        contractors: [{ company_id: 'c_nng', name: 'АО «ННГ»', rating: 5, justification: 'Рейтинг 5, выполнено 14 аналогичных работ' }],
        similar_requests: [{ request_id: 'r_0006', title: 'Сейсморазведка 3D и концепт развития Малоямальского', similarity: 0.71, status: 'submitted' }],
      },
      created_at: '2026-06-03T09:15:40Z',
    },
  ]

  return {
    users,
    companies,
    contracts,
    products,
    contract_products,
    product_rates,
    product_operations,
    cost_calculations,
    calculation_stages,
    templates,
    requests,
    tzs: [tz1, tz2, tz3, tz4],
    analyses,
    documents,
    chat_sessions,
    chat_messages,
    jobs: [],
    counters: { request: 7 },
  }
}
