import { beforeEach, describe, expect, it, vi } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../msw/server'
import { useAuthStore } from '@/lib/stores/authStore'

const user = { id: 'u-1', username: 'ivanov', role: 'customer' as const }

describe('useAuthStore (Zustand)', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, token: null })
    window.localStorage.clear()
  })

  it('login: сохраняет token и user в store и localStorage', async () => {
    // Arrange
    server.use(
      http.post('*/api/v1/auth/login', () =>
        HttpResponse.json({ access_token: 'jwt-abc', user }),
      ),
    )

    // Act
    const loggedIn = await useAuthStore.getState().login('ivanov')

    // Assert
    const state = useAuthStore.getState()
    expect(loggedIn.username).toBe('ivanov')
    expect(state.token).toBe('jwt-abc')
    expect(state.user?.id).toBe('u-1')
    expect(window.localStorage.getItem('prostor.token')).toBe('jwt-abc')
    expect(JSON.parse(window.localStorage.getItem('prostor.user') ?? '{}')).toEqual({ ...user, full_name: 'ivanov' })
  })

  it('logout: чистит store и localStorage', () => {
    // Arrange
    window.localStorage.setItem('prostor.token', 'jwt-abc')
    window.localStorage.setItem('prostor.user', JSON.stringify(user))
    useAuthStore.setState({ user, token: 'jwt-abc' })

    // Act
    useAuthStore.getState().logout()

    // Assert
    expect(useAuthStore.getState().user).toBeNull()
    expect(useAuthStore.getState().token).toBeNull()
    expect(window.localStorage.getItem('prostor.token')).toBeNull()
    expect(window.localStorage.getItem('prostor.user')).toBeNull()
  })

  it('login: пробрасывает ошибку API при неудаче', async () => {
    // Arrange
    server.use(
      http.post('*/api/v1/auth/login', () =>
        HttpResponse.json({ error: { code: 'VALIDATION', message: 'нет username', details: null } }, { status: 400 }),
      ),
    )

    // Act / Assert
    await expect(useAuthStore.getState().login('')).rejects.toThrow('нет username')
    expect(useAuthStore.getState().token).toBeNull()
  })
})
