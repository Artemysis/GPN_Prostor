import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../msw/server'
import { JOB_ID, REQUEST_ID } from '../utils/fixtures'
import { renderWithProviders } from '../utils/renderWithProviders'
import { TzBlockCard } from '@/components/requests/TzBlockCard'
import type { TzBlock, TzTemplateBlockSchema } from '@/lib/api'
import { useUiStore } from '@/lib/stores/uiStore'

const schema: TzTemplateBlockSchema = {
  code: 'goals',
  name: 'Цели и задачи работ',
  order: 1,
  fields: [
    { key: 'goal_text', type: 'text', label: 'Цель', required: true },
    { key: 'tasks', type: 'list', label: 'Задачи' },
  ],
}

function makeBlock(overrides: Partial<TzBlock> = {}): TzBlock {
  return {
    block_code: 'goals',
    block_name: 'Цели и задачи работ',
    content: { goal_text: 'Оценка запасов' },
    filled_by: 'manual',
    is_complete: false,
    completeness_pct: 50,
    ...overrides,
  }
}

function renderCard(block: TzBlock) {
  return renderWithProviders(<TzBlockCard block={block} schema={schema} requestId={REQUEST_ID} />)
}

describe('TzBlockCard (filled_by)', () => {
  it('manual — без бейджа, ai — «ИИ», mixed — «ИИ + правки»', () => {
    const { unmount } = renderCard(makeBlock())
    expect(screen.queryByText('ИИ')).not.toBeInTheDocument()
    expect(screen.queryByText('ИИ + правки')).not.toBeInTheDocument()
    unmount()

    renderCard(makeBlock({ filled_by: 'ai' }))
    expect(screen.getByText('ИИ')).toBeInTheDocument()
    expect(screen.queryByText('ИИ + правки')).not.toBeInTheDocument()
    unmount()

    renderCard(makeBlock({ filled_by: 'mixed' }))
    expect(screen.getByText('ИИ + правки')).toBeInTheDocument()
  })

  it('правка поля показывает баннер, сохранение шлёт PATCH с filled_by=manual', async () => {
    const user = userEvent.setup()
    let saved: Record<string, unknown> | null = null
    server.use(
      http.patch(`*/api/v1/requests/${REQUEST_ID}/tz/blocks/goals`, async ({ request }) => {
        saved = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({})
      }),
    )
    renderCard(makeBlock())

    const goal = screen.getByLabelText(/Цель/i) as HTMLTextAreaElement
    await user.clear(goal)
    await user.type(goal, 'Новая цель')
    expect(screen.getByText('Есть несохраненные правки')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: /Сохранить/i })[0])

    await waitFor(() => expect(saved).not.toBeNull())
    expect(saved).toMatchObject({
      content: { goal_text: 'Новая цель' },
      filled_by: 'manual',
    })
    expect(screen.queryByText('Есть несохраненные правки')).not.toBeInTheDocument()
    expect(useUiStore.getState().toasts.some((t) => t.message.includes('сохранен'))).toBe(true)
  })

  it('сохранение вручную поверх ИИ даёт бейдж «ИИ + правки»', async () => {
    const user = userEvent.setup()
    server.use(
      http.patch(`*/api/v1/requests/${REQUEST_ID}/tz/blocks/goals`, () => HttpResponse.json({})),
    )
    renderCard(makeBlock({ filled_by: 'ai' }))
    expect(screen.getByText('ИИ')).toBeInTheDocument()

    const goal = screen.getByLabelText(/Цель/i)
    await user.type(goal, '!')
    await user.click(screen.getAllByRole('button', { name: /Сохранить/i })[0])

    await waitFor(() => expect(screen.getByText('ИИ + правки')).toBeInTheDocument())
  })

  it('«Заполнить ИИ»: job-поллинг, черновик и применение с filled_by=ai', async () => {
    const user = userEvent.setup()
    let saved: Record<string, unknown> | null = null
    server.use(
      http.post(`*/api/v1/requests/${REQUEST_ID}/tz/blocks/goals/fill-ai`, () =>
        HttpResponse.json({ job_id: JOB_ID }),
      ),
      http.get(`*/api/v1/jobs/${JOB_ID}`, () =>
        HttpResponse.json({
          id: JOB_ID,
          type: 'fill_ai',
          status: 'done',
          result: {
            block_code: 'goals',
            content: { goal_text: 'Цель от ИИ', tasks: ['Задача ИИ'] },
          },
          error: null,
        }),
      ),
      http.patch(`*/api/v1/requests/${REQUEST_ID}/tz/blocks/goals`, async ({ request }) => {
        saved = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({})
      }),
    )
    renderCard(makeBlock({ content: {} }))

    await user.click(screen.getByRole('button', { name: /Заполнить ИИ/i }))

    // черновик ИИ появился со старым (пустым) и предложенным значением
    expect(await screen.findByText('Черновик ИИ — проверьте и примените')).toBeInTheDocument()
    expect(screen.getByText('Цель от ИИ')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Применить/i }))

    await waitFor(() => expect(saved).not.toBeNull())
    expect(saved).toMatchObject({
      content: { goal_text: 'Цель от ИИ', tasks: ['Задача ИИ'] },
      filled_by: 'ai',
    })
    // после применения блок помечен как ИИ
    await waitFor(() => expect(screen.getByText('ИИ')).toBeInTheDocument())
  })

  it('ошибка job-а показывает toast и не ломает блок', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`*/api/v1/requests/${REQUEST_ID}/tz/blocks/goals/fill-ai`, () =>
        HttpResponse.json({ job_id: JOB_ID }),
      ),
      http.get(`*/api/v1/jobs/${JOB_ID}`, () =>
        HttpResponse.json({ id: JOB_ID, type: 'fill_ai', status: 'failed', result: null, error: 'boom' }),
      ),
    )
    renderCard(makeBlock({ content: {} }))

    await user.click(screen.getByRole('button', { name: /Заполнить ИИ/i }))

    await waitFor(() =>
      expect(useUiStore.getState().toasts.some((t) => t.message === 'ИИ не смог заполнить блок')).toBe(true),
    )
    expect(screen.queryByText('Черновик ИИ — проверьте и примените')).not.toBeInTheDocument()
  })
})
