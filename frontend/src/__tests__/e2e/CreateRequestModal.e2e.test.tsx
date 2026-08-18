import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../msw/server'
import { makeRequest, makeTz } from '../utils/fixtures'
import { renderWithProviders } from '../utils/renderWithProviders'
import { CreateRequestModal } from '@/components/requests/CreateRequestModal'
import { useUiStore } from '@/lib/stores/uiStore'

/**
 * E2E визарда создания заявки:
 * автосоздание черновика → шапка → выбор типа ТЗ (пин цветом) → конструктор ТЗ →
 * возврат на шаг 1 (выбор закреплён) → отправка заявки.
 */
describe('CreateRequestModal — полный сценарий', () => {
  it('проходит путь от черновика до отправленной заявки', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    // Живое состояние «сервера»: заявка и ТЗ
    let request = makeRequest({ id: 'req-e2e-1', number: 'REQ-2026-000001' })
    let tz: ReturnType<typeof makeTz> | null = null
    const requestDetail = () => ({
      ...request,
      tz_summary: { completeness_pct: tz?.completeness_pct ?? 0, risks_count: 0 },
      documents_count: 0,
    })

    server.use(
      http.post('*/api/v1/requests', () => HttpResponse.json(request)),
      http.get('*/api/v1/requests/req-e2e-1', () => HttpResponse.json(requestDetail())),
      http.patch('*/api/v1/requests/req-e2e-1', async ({ request: req }) => {
        request = { ...request, ...(await req.json()) as object, updated_at: new Date().toISOString() }
        return HttpResponse.json(request)
      }),
      http.post('*/api/v1/requests/req-e2e-1/submit', () => {
        request = { ...request, status: 'submitted' }
        return HttpResponse.json(request)
      }),
      http.get('*/api/v1/requests/req-e2e-1/tz', () =>
        tz ? HttpResponse.json(tz) : new HttpResponse(null, { status: 404 }),
      ),
      http.post('*/api/v1/requests/req-e2e-1/tz', () => {
        tz = makeTz({ completeness_pct: 10 })
        return HttpResponse.json(tz)
      }),
      http.post('*/api/v1/chat/sessions', () => HttpResponse.json({ session_id: 'sess-e2e' })),
      http.get('*/api/v1/chat/sessions/sess-e2e/messages', () => HttpResponse.json([])),
    )

    renderWithProviders(<CreateRequestModal open onClose={onClose} />)
    const user0 = user

    // --- Шаг 1: черновик создан автоматически, форма шапки видна ---
    expect(await screen.findByText(/REQ-2026-000001/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Название заявки/i)).toBeInTheDocument()
    expect(screen.getByText('1. Шапка заявки')).toBeInTheDocument()

    // --- Заполняем шапку и сохраняем ---
    const title = screen.getByLabelText(/Название заявки/i)
    await user0.clear(title)
    await user0.type(title, 'Подсчёт запасов УВС')
    await user0.click(screen.getByRole('button', { name: /Сохранить/i }))
    await waitFor(() =>
      expect(useUiStore.getState().toasts.some((t) => t.message === 'Шапка заявки сохранена')).toBe(true),
    )

    // --- Выбираем тип ТЗ карточкой: создание и автопереход в конструктор ---
    // (пин «✓ Выбрано» проверяем после возврата на шаг 1 — до этого список размонтируется)
    await user0.click(await screen.findByRole('button', { name: /ТЗ ПТД/ }))
    // ТЗ создан на сервере
    await waitFor(() => expect(tz).not.toBeNull())
    // автопереход на шаг 2: конструктор ТЗ с блоками шаблона
    expect(await screen.findByText('Цели и задачи работ')).toBeInTheDocument()
    expect(await screen.findByText(/готовность ТЗ/i)).toBeInTheDocument()

    // --- Возврат на шаг 1: выбор типа закреплён, есть продолжение работы ---
    await user0.click(screen.getByRole('button', { name: /← Изменить шапку заявки/i }))
    expect(await screen.findByText('✓ Выбрано')).toBeInTheDocument() // цвет восстановлен из ТЗ
    expect((screen.getByLabelText(/Название заявки/i) as HTMLInputElement).value).toBe('Подсчёт запасов УВС')
    await user0.click(screen.getByRole('button', { name: /Продолжить работу с ТЗ/i }))

    // --- Шаг 2 снова: отправляем заявку ---
    expect(await screen.findByText('Цели и задачи работ')).toBeInTheDocument()
    const submit = screen.getByRole('button', { name: /Отправить заявку/i })
    expect(submit).toBeEnabled()
    await user0.click(submit)

    await waitFor(() =>
      expect(useUiStore.getState().toasts.some((t) => t.message === 'Заявка отправлена')).toBe(true),
    )
    // статус-бейдж и кнопка переключились на «Отправлена»
    expect(await screen.findAllByText('Отправлена')).toHaveLength(2)
    expect(request.status).toBe('submitted')
  })
})
