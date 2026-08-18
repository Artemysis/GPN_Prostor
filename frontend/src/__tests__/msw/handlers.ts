import { http, HttpResponse } from 'msw'
import { companies, contracts, products, template, templatesSummary } from '../utils/fixtures'

/** Стандартные MSW-хендлеры каталога: компании, договоры, продукты, шаблоны */
export const catalogHandlers = [
  http.get('*/api/v1/companies', () => HttpResponse.json(companies)),
  http.get('*/api/v1/contracts', () => HttpResponse.json(contracts)),
  http.get('*/api/v1/products', () => HttpResponse.json(products)),
  http.get('*/api/v1/tz-templates', () => HttpResponse.json(templatesSummary)),
  http.get('*/api/v1/tz-templates/:id', () => HttpResponse.json(template)),
]
