import { describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatMessageView } from '@/components/requests/ChatMessage'
import { makeChatMessage } from '../utils/fixtures'
import { renderWithProviders } from '../utils/renderWithProviders'
import type { ChatAction } from '@/lib/api'

const onApply = vi.fn()

function renderMessage(actions: ChatAction[] | null, streaming = false) {
  return renderWithProviders(
    <ChatMessageView
      message={makeChatMessage({ actions, content: 'Текст ответа' })}
      streaming={streaming}
      onApply={onApply}
    />,
  )
}

describe('ChatMessageView', () => {
  it('рендерит пользовательское сообщение без панели действий', () => {
    renderWithProviders(
      <ChatMessageView message={makeChatMessage({ role: 'user', content: 'нужен ГРП' })} onApply={onApply} />,
    )

    expect(screen.getByText('нужен ГРП')).toBeInTheDocument()
    expect(screen.queryByText('Предложения ИИ — подтвердите применение')).not.toBeInTheDocument()
    expect(screen.getByText('ВЫ')).toBeInTheDocument()
  })

  it('рендерит карточки рекомендаций: продукты, исполнители, похожие заявки', () => {
    renderWithProviders(
      <ChatMessageView
        message={makeChatMessage({
          suggestions: {
            products: [{ product_id: 'P-1', product_name: 'Гидравлический разрыв пласта', justification: 'по запросу' }],
            contractors: [{ company_id: 'C-1', name: 'ГеоСервис', rating: 5, justification: 'рейтинг' }],
            similar_requests: [{ request_id: 'req-9', title: 'Геомодель УВС', similarity: 0.82, status: 'ready' }],
          },
        })}
        onApply={onApply}
      />,
    )

    expect(screen.getByText('Продукты')).toBeInTheDocument()
    expect(screen.getByText('Гидравлический разрыв пласта')).toBeInTheDocument()
    expect(screen.getByText('Исполнители')).toBeInTheDocument()
    expect(screen.getByText('ГеоСервис')).toBeInTheDocument()
    expect(screen.getByText('Похожие заявки')).toBeInTheDocument()
    expect(screen.getByText('схожесть 82%')).toBeInTheDocument()
  })

  it('скрывает панель действий во время стриминга', () => {
    renderMessage([{ type: 'set_field', field: 'product_id', value: 'P-1', confidence: 0.9 }], true)

    expect(screen.getByText('ИИ печатает…')).toBeInTheDocument()
    expect(screen.queryByText('Предложения ИИ — подтвердите применение')).not.toBeInTheDocument()
  })

  it('показывает предложения полей: резолвит id по справочникам, применённое — залочено', async () => {
    renderMessage([
      { type: 'set_field', field: 'company_id', value: 'C-1', confidence: 0.9 },
      { type: 'set_field', field: 'product_id', value: 'P-1', confidence: 0.8, applied: true },
    ])

    // значения резолвлены через справочники
    expect(await screen.findByText('ГеоСервис')).toBeInTheDocument()
    expect(await screen.findByText('Гидравлический разрыв пласта')).toBeInTheDocument()
    expect(screen.getByText('уверенность 90%')).toBeInTheDocument()
    // применённое показано бейджем, чекбокс залочен
    expect(screen.getByText('применено')).toBeInTheDocument()
    const boxes = screen.getAllByRole('checkbox')
    expect(boxes).toHaveLength(2)
    const appliedCheckbox = boxes.find((b) => (b as HTMLInputElement).disabled)
    expect(appliedCheckbox).toBeDefined()
    expect((appliedCheckbox as HTMLInputElement).checked).toBe(true)
  })

  it('«Применить выбранные» отправляет только отмеченные экшены', async () => {
    const user = userEvent.setup()
    renderActionPanel([
      { type: 'set_field', field: 'company_id', value: 'C-1', confidence: 0.9 },
      { type: 'set_field', field: 'title', value: 'Геомодель', confidence: 0.7 },
    ])

    const btn = await screen.findByRole('button', { name: 'Применить выбранные (2)' })
    // снимаем вторую галочку
    await user.click(screen.getAllByRole('checkbox')[1])
    expect(screen.getByRole('button', { name: 'Применить выбранные (1)' })).toBeEnabled()

    await user.click(btn)
    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1))
    const sent = onApply.mock.calls[0][0] as ChatAction[]
    expect(sent).toHaveLength(1)
    expect(sent[0]).toMatchObject({ field: 'company_id', value: 'C-1' })
  })

  it('suggest_template вместе с полями: без кнопки «Создать ТЗ», шаблон уходит в onApply', async () => {
    const user = userEvent.setup()
    renderActionPanel([
      { type: 'set_field', field: 'company_id', value: 'C-1', confidence: 0.9 },
      { type: 'suggest_template', template_id: 'T-1', confidence: 0.85 },
    ])

    // карточка рекомендации появилась, отдельной кнопки создания нет
    expect(await screen.findByText(/Рекомендация шаблона ТЗ:/)).toBeInTheDocument()
    expect(screen.getByText('ТЗ ПТД')).toBeInTheDocument()
    expect(screen.getByText(/шаблон применится вместе с предложениями выше/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Создать ТЗ/ })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Применить и создать ТЗ (1)' }))
    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1))
    const sent = onApply.mock.calls[0][0] as ChatAction[]
    expect(sent).toHaveLength(2) // выбранное поле + шаблон
    expect(sent.some((a) => a.type === 'suggest_template' && a.template_id === 'T-1')).toBe(true)
  })

  it('suggest_template без полей: единственная кнопка «Применить» отправляет только шаблон', async () => {
    const user = userEvent.setup()
    renderActionPanel([{ type: 'suggest_template', template_id: 'T-1', confidence: 0.85 }])

    await user.click(await screen.findByRole('button', { name: 'Применить' }))
    await waitFor(() => expect(onApply).toHaveBeenCalledTimes(1))
    expect(onApply.mock.calls[0][0]).toEqual([
      { type: 'suggest_template', template_id: 'T-1', confidence: 0.85 },
    ])
  })
})

function renderActionPanel(actions: ChatAction[]) {
  return renderMessage(actions, false)
}
