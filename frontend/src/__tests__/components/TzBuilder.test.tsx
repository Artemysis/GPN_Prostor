import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { makeStage, makeTz, REQUEST_ID } from '../utils/fixtures'
import { renderWithProviders } from '../utils/renderWithProviders'
import { TzBuilder } from '@/components/requests/TzBuilder'

describe('TzBuilder', () => {
  it('рендерит блоки по порядку шаблона, независимо от порядка в ТЗ', async () => {
    // makeTz отдаёт блоки в обратном порядке (signatures первым)
    renderWithProviders(<TzBuilder requestId={REQUEST_ID} tz={makeTz()} />)

    const names = [
      'Цели и задачи работ',
      'Периметр работ',
      'Содержание работ',
      'Подписи сторон',
    ]
    for (const name of names) {
      expect(await screen.findByText(name)).toBeInTheDocument()
    }
    // порядок в DOM соответствует порядку шаблона
    const positions = names.map((n) => screen.getByText(n).compareDocumentPosition(screen.getByText(names[0])))
    const before = positions.filter((p) => p & Node.DOCUMENT_POSITION_PRECEDING)
    expect(before).toHaveLength(names.length - 1) // все, кроме первого, идут после «Цели и задачи»
  })

  it('блок этапов рендерится редактором этапов с готовностью', async () => {
    renderWithProviders(
      <TzBuilder
        requestId={REQUEST_ID}
        tz={makeTz({
          stages: [makeStage({ stage_order: 1, stage_name: 'Формирование базы данных', requirements: 'данные' })],
        })}
      />,
    )

    expect(await screen.findByText('Формирование базы данных')).toBeInTheDocument()
    expect(screen.getByText(/этапов: 1/)).toBeInTheDocument()
    expect(screen.getByText('Требования: данные')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Дополнить ИИ/i })).toBeInTheDocument()
  })

  it('обычный блок рендерит поля схемы с обязательными метками', async () => {
    renderWithProviders(
      <TzBuilder
        requestId={REQUEST_ID}
        tz={makeTz({
          blocks: [
            { block_code: 'goals', block_name: 'Цели и задачи работ', content: {}, filled_by: 'manual', is_complete: false, completeness_pct: 0 },
          ],
        })}
      />,
    )

    expect(await screen.findByText('Цель')).toBeInTheDocument()
    expect(screen.getAllByText('*')).toHaveLength(2) // оба поля обязательны
    expect(screen.getByText('Задачи')).toBeInTheDocument()
  })
})
