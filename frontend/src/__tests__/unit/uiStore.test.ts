import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useUiStore } from '@/lib/stores/uiStore'

describe('useUiStore (Zustand, тосты)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useUiStore.setState({ toasts: [] })
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('toast: добавляет тост с kind по умолчанию info', () => {
    // Arrange / Act
    useUiStore.getState().toast('Сохранено')

    // Assert
    const toasts = useUiStore.getState().toasts
    expect(toasts).toHaveLength(1)
    expect(toasts[0]).toMatchObject({ message: 'Сохранено', kind: 'info' })
  })

  it('toast: авто-скрытие через 4200 мс', () => {
    // Arrange
    useUiStore.getState().toast('Ошибка', 'error')
    expect(useUiStore.getState().toasts).toHaveLength(1)

    // Act
    vi.advanceTimersByTime(4300)

    // Assert
    expect(useUiStore.getState().toasts).toHaveLength(0)
  })

  it('dismiss: удаляет конкретный тост по id', () => {
    // Arrange
    useUiStore.getState().toast('первый')
    useUiStore.getState().toast('второй', 'success')
    const [first] = useUiStore.getState().toasts

    // Act
    useUiStore.getState().dismiss(first.id)

    // Assert
    const rest = useUiStore.getState().toasts
    expect(rest).toHaveLength(1)
    expect(rest[0].message).toBe('второй')
  })
})
