import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../msw/server'
import { companies, contracts, makeRequest, products } from '../utils/fixtures'
import { renderWithProviders } from '../utils/renderWithProviders'
import { RequestHeaderForm } from '@/components/requests/RequestHeaderForm'
import { fireEvent } from '@testing-library/react'
import { useUiStore } from '@/lib/stores/uiStore'

const onSaved = vi.fn()

function renderForm(overrides: Parameters<typeof makeRequest>[0] = {}) {
  return renderWithProviders(<RequestHeaderForm request={makeRequest(overrides)} onSaved={onSaved} />)
}

describe('RequestHeaderForm', () => {
  it('подставляет существующие значения заявки', async () => {
    renderForm({ title: 'Подсчёт запасов', description: 'Описание работ', cost_total: 24500000 })

    expect((screen.getByLabelText(/Название заявки/i) as HTMLInputElement).value).toBe('Подсчёт запасов')
    expect((screen.getByLabelText(/Описание/i) as HTMLTextAreaElement).value).toBe('Описание работ')
    expect((screen.getByLabelText(/Стоимость/i) as HTMLInputElement).value).toBe('24500000')
    // каталоги подгрузились
    expect(await screen.findByText(/ГеоСервис — рейтинг 5/)).toBeInTheDocument()
  })

  it('каскад: выбор исполнителя фильтрует договоры, договор — продукты', async () => {
    const user = userEvent.setup()
    server.use(
      http.get('*/api/v1/contracts', ({ request }) => {
        const companyId = new URL(request.url).searchParams.get('company_id')
        const items = companyId ? contracts.filter((k) => k.company_id === companyId) : contracts
        return HttpResponse.json(items)
      }),
      http.get('*/api/v1/products', ({ request }) => {
        const contractId = new URL(request.url).searchParams.get('contract_id')
        const items = contractId ? products.filter((p) => p.product_id === 'P-1') : products
        return HttpResponse.json(items)
      }),
    )
    renderForm()

    const company = await screen.findByLabelText(/Исполнитель/i)
    const contract = screen.getByLabelText(/Договор/i) as HTMLSelectElement
    const product = screen.getByLabelText(/Продукт/i) as HTMLSelectElement

    // до выбора исполнителя договор недоступен
    expect(contract).toBeDisabled()
    await screen.findByText(/ГеоСервис — рейтинг 5/) // каталог загружен
    await user.selectOptions(company, 'C-1')
    expect(contract).toBeEnabled()
    // в списке только договоры ГеоСервиса
    expect([...contract.options].map((o) => o.value)).toEqual(['', 'K-1'])

    await user.selectOptions(contract, 'K-1')
    expect(product).toBeEnabled()
    expect([...product.options].map((o) => o.value)).toEqual(['', 'P-1'])
  })

  it('валидация: короткое название и дата окончания раньше начала не уходят на сервер', async () => {
    const user = userEvent.setup()
    const patch = vi.fn()
    server.use(http.patch('*/api/v1/requests/*', () => {
      patch()
      return HttpResponse.json({})
    }))
    renderForm()

    // короткий title
    const title = screen.getByLabelText(/Название заявки/i)
    await user.clear(title)
    await user.type(title, 'ГР')
    fireEvent.submit(title.closest('form')!)

    expect(await screen.findByText('Укажите название (минимум 3 символа)')).toBeInTheDocument()
    expect(patch).not.toHaveBeenCalled()

    // корректный title, но даты в обратном порядке
    await user.clear(title)
    await user.type(title, 'Геомодель')
    fireEvent.change(screen.getByLabelText(/Начало работ/i), { target: { value: '2026-02-01' } })
    fireEvent.change(screen.getByLabelText(/Окончание работ/i), { target: { value: '2026-01-01' } })
    fireEvent.submit(title.closest('form')!)

    expect(await screen.findByText('Дата окончания раньше даты начала')).toBeInTheDocument()
    expect(patch).not.toHaveBeenCalled()
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('сохранение: PATCH с нормализованными значениями, onSaved вызван', async () => {
    const user = userEvent.setup()
    let saved: Record<string, unknown> | null = null
    server.use(
      http.patch('*/api/v1/requests/*', async ({ request }) => {
        saved = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({})
      }),
    )
    renderForm()

    const title = screen.getByLabelText(/Название заявки/i)
    await user.clear(title)
    await user.type(title, 'Подсчёт запасов и 3D геомодель')
    fireEvent.change(screen.getByLabelText(/Стоимость/i), { target: { value: '24500000' } })
    await user.click(screen.getByRole('button', { name: /Сохранить/i }))

    await waitFor(() => expect(saved).not.toBeNull())
    expect(saved).toMatchObject({
      title: 'Подсчёт запасов и 3D геомодель',
      cost_total: 24500000, // строка → число
      company_id: null, // пустые селекты → null
    })
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1))
    expect(useUiStore.getState().toasts.some((t) => t.message === 'Шапка заявки сохранена')).toBe(true)
  })
})
