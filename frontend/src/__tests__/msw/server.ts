import { setupServer } from 'msw/node'
import { catalogHandlers } from './handlers'

/** Общий MSW-сервер: базовые хендлеры каталога + серверные (server.use) в тестах.
 *  resetHandlers() в afterEach возвращает именно этот набор. */
export const server = setupServer(...catalogHandlers)
