import { mockApi } from './mock'

export const api = mockApi

export function resetDemoData() {
  mockApi.reset()
}

export * from './types'
