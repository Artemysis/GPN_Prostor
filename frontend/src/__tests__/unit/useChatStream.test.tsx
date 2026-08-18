import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../msw/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { useChatStream } from '@/lib/hooks/useChatStream'
import { CHAT_SESSION_ID, sseBody } from '../utils/fixtures'

const history = [
  { id: 'm-1', role: 'user', content: 'нужен ГРП', actions: null, created_at: '2026-01-01T00:00:00Z' },
]

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

describe('useChatStream', () => {
  it('загружает историю при появлении sessionId', async () => {
    // Arrange
    server.use(
      http.get(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, () =>
        HttpResponse.json(
          history.map((m) => ({ ...m, session_id: CHAT_SESSION_ID })),
        ),
      ),
    )
    const { result } = renderHook(() => useChatStream(CHAT_SESSION_ID), { wrapper: createWrapper() })

    // Act / Assert
    await waitFor(() => expect(result.current.messages).toHaveLength(1))
    expect(result.current.messages[0].content).toBe('нужен ГРП')
    expect(result.current.streaming).toBe(false)
  })

  it('send: стримит delta, сохраняет suggestions и actions из SSE', async () => {
    // Arrange — новая сессия: история пуста, наполняется сервером после отправки
    const persisted: { id: string; role: string; content: string; actions: unknown; created_at: string }[] = []
    server.use(
      http.get(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, () => HttpResponse.json(persisted)),
      http.post(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, async ({ request }) => {
        const { content } = (await request.json()) as { content: string }
        persisted.push({ id: 'srv-m-1', role: 'user', content, actions: null, created_at: '2026-01-01T00:00:00Z' })
        persisted.push({
          id: 'srv-m-2',
          role: 'assistant',
          content: 'Разобрал запрос.',
          actions: [{ type: 'set_field', field: 'product_id', value: 'P-1', confidence: 0.9 }],
          created_at: '2026-01-01T00:00:01Z',
        })
        return new HttpResponse(
          sseBody(
            { type: 'delta', content: 'Разобрал ' },
            { type: 'delta', content: 'запрос.' },
            { type: 'products', items: [{ product_id: 'P-1', product_name: 'ГРП', justification: 'совпадение' }] },
            { type: 'actions', actions: [{ type: 'set_field', field: 'product_id', value: 'P-1', confidence: 0.9 }] },
          ),
          { headers: { 'Content-Type': 'text/event-stream' } },
        )
      }),
    )
    const { result } = renderHook(() => useChatStream(CHAT_SESSION_ID), { wrapper: createWrapper() })

    // Act
    await act(async () => {
      await result.current.send('нужен ГРП')
    })

    // Assert
    const messages = result.current.messages
    expect(messages).toHaveLength(2)
    expect(messages[0].role).toBe('user')
    expect(messages[0].content).toBe('нужен ГРП')
    const assistant = messages[1]
    expect(assistant.role).toBe('assistant')
    expect(assistant.content).toBe('Разобрал запрос.') // чанки delta склеены
    expect(assistant.suggestions?.products?.[0].product_name).toBe('ГРП') // suggestions сохранены поверх истории
    expect(assistant.actions?.[0]).toMatchObject({ field: 'product_id', value: 'P-1' })
    expect(result.current.streaming).toBe(false)
  })

  it('send: игнорирует пустой ввод', async () => {
    // Arrange
    server.use(
      http.get(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, () => HttpResponse.json([])),
    )
    const { result } = renderHook(() => useChatStream(CHAT_SESSION_ID), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.messages).toHaveLength(0))

    // Act
    await act(async () => {
      await result.current.send('   ')
    })

    // Assert
    expect(result.current.messages).toHaveLength(0) // ничего не отправлено
  })

  it('applyActions: помечает применённые экшены', async () => {
    // Arrange
    server.use(
      http.get(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, () => HttpResponse.json([])),
      http.post(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/apply`, () =>
        HttpResponse.json({ applied: [{ field: 'product_id', old: null, new: 'P-1' }] }),
      ),
    )
    const { result } = renderHook(() => useChatStream(CHAT_SESSION_ID), { wrapper: createWrapper() })
    const action = { type: 'set_field' as const, field: 'product_id', value: 'P-1', confidence: 0.9 }

    // Act
    let applied: { field: string }[] = []
    await act(async () => {
      applied = await result.current.applyActions([action])
    })

    // Assert
    expect(applied).toEqual([{ field: 'product_id', old: '—', new: 'P-1' }])
  })
})
