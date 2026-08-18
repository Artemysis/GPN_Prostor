import { setupServer } from 'msw/node'
import type { HttpHandler } from 'msw'

/** Общий MSW-сервер для всех тестов. Хендлеры регистрируются через server.use(). */
export const server = setupServer(...([] as HttpHandler[]))
