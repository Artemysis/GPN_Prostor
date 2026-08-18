import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../msw/server'
import { CHAT_SESSION_ID, REQUEST_ID, sseBody } from '../utils/fixtures'
import { renderWithProviders } from '../utils/renderWithProviders'
import { AiChat } from '@/components/requests/AiChat'
import { useUiStore } from '@/lib/stores/uiStore'

function stubSession() {
  server.use(
    http.post('*/api/v1/chat/sessions', () => HttpResponse.json({ session_id: CHAT_SESSION_ID })),
  )
}

describe('AiChat', () => {
  it('создаёт сессию и показывает историю сообщений', async () => {
    stubSession()
    server.use(
      http.get(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, () =>
        HttpResponse.json([
          { id: 'm-1', role: 'user', content: 'нужен ГРП', actions: null, created_at: '2026-01-01T00:00:00Z' },
          { id: 'm-2', role: 'assistant', content: 'Разобрал запрос', actions: null, created_at: '2026-01-01T00:00:01Z' },
        ]),
      ),
    )
    renderWithProviders(<AiChat requestId={REQUEST_ID} />)

    expect(await screen.findByText('ИИ-консультант')).toBeInTheDocument()
    expect(await screen.findByText('нужен ГРП')).toBeInTheDocument()
    expect(screen.getByText('Разобрал запрос')).toBeInTheDocument()
    expect(screen.queryByText(/Опишите задачу/)).not.toBeInTheDocument() // подсказка скрыта историей
  })

  it('SSE: отправка стримит дельты и карточки рекомендаций в интерфейс', async () => {
    stubSession()
    // сервер сохраняет сообщения: после стрима useChatStream перечитывает историю
    const persisted: unknown[] = []
    server.use(
      http.get(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, () => HttpResponse.json(persisted)),
      http.post(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, async ({ request }) => {
        const { content } = (await request.json()) as { content: string }
        persisted.push({ id: 'srv-m-1', role: 'user', content, actions: null, created_at: '2026-01-01T00:00:00Z' })
        persisted.push({
          id: 'srv-m-2',
          role: 'assistant',
          content: 'Предлагаю ГРП.',
          actions: [{ type: 'set_field', field: 'product_id', value: 'P-1', confidence: 0.9 }],
          created_at: '2026-01-01T00:00:01Z',
        })
        return new HttpResponse(
          sseBody(
            { type: 'delta', content: 'Предлагаю ' },
            { type: 'delta', content: 'ГРП.' },
            { type: 'products', items: [{ product_id: 'P-1', product_name: 'Гидравлический разрыв пласта', justification: 'по запросу' }] },
            { type: 'actions', actions: [{ type: 'set_field', field: 'product_id', value: 'P-1', confidence: 0.9 }] },
          ),
          { headers: { 'Content-Type': 'text/event-stream' } },
        )
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<AiChat requestId={REQUEST_ID} />)

    const input = await screen.findByPlaceholderText(/Спросите ИИ/i)
    await user.type(input, 'нужен ГРП{Enter}') // Enter в поле отправляет сообщение

    // дельты склеились в один ответ
    expect(await screen.findByText('Предлагаю ГРП.')).toBeInTheDocument()
    // карточка продуктов + то же значение в панели предложений
    expect(await screen.findAllByText('Гидравлический разрыв пласта')).toHaveLength(2)
    expect(await screen.findByText('Предложения ИИ — подтвердите применение')).toBeInTheDocument()
  })

  it('onTemplateRecommended поднимает последнюю рекомендацию шаблона из истории', async () => {
    stubSession()
    const recommended = vi.fn()
    server.use(
      http.get(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, () =>
        HttpResponse.json([
          {
            id: 'm-2',
            role: 'assistant',
            content: 'рекомендую ПТД',
            actions: [{ type: 'suggest_template', template_id: 'T-1', confidence: 0.9 }],
            created_at: '2026-01-01T00:00:01Z',
          },
        ]),
      ),
    )
    renderWithProviders(<AiChat requestId={REQUEST_ID} onTemplateRecommended={recommended} />)

    await waitFor(() => expect(recommended).toHaveBeenCalledWith('T-1'))
  })

  it('применение предложений: POST /apply, toast и onApplied с tz_diff', async () => {
    stubSession()
    const onApplied = vi.fn()
    server.use(
      http.get(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/messages`, () =>
        HttpResponse.json([
          {
            id: 'm-2',
            role: 'assistant',
            content: 'предлагаю',
            actions: [
              { type: 'set_field', field: 'product_id', value: 'P-1', confidence: 0.9 },
              { type: 'suggest_template', template_id: 'T-1', confidence: 0.8 },
            ],
            created_at: '2026-01-01T00:00:01Z',
          },
        ]),
      ),
      http.post(`*/api/v1/chat/sessions/${CHAT_SESSION_ID}/apply`, () =>
        HttpResponse.json({
          applied: [{ field: 'product_id', old: null, new: 'P-1' }],
          request_diff: { product_id: 'P-1' },
          tz_diff: { tz_id: 'tz-9', template_id: 'T-1', completeness_pct: 25 },
        }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<AiChat requestId={REQUEST_ID} onApplied={onApplied} />)

    await user.click(await screen.findByRole('button', { name: /Применить и создать ТЗ/ }))

    await waitFor(() => expect(onApplied).toHaveBeenCalledTimes(1))
    expect(onApplied.mock.calls[0][0].tz_diff).toMatchObject({ tz_id: 'tz-9' })
    expect(
      useUiStore.getState().toasts.some((t) => t.message.includes('ТЗ создано')),
    ).toBe(true)
  })
})
