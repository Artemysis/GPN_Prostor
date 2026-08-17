import { create } from 'zustand'
import { api } from '@/lib/api'
import type { User } from '@/lib/api'

interface AuthState {
  user: User | null
  token: string | null
  login: (username: string) => Promise<User>
  logout: () => void
}

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem('prostor.user')
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  user: readStoredUser(),
  token: localStorage.getItem('prostor.token'),
  login: async (username) => {
    const { access_token, user } = await api.login(username)
    localStorage.setItem('prostor.token', access_token)
    localStorage.setItem('prostor.user', JSON.stringify(user))
    set({ user, token: access_token })
    return user
  },
  logout: () => {
    localStorage.removeItem('prostor.token')
    localStorage.removeItem('prostor.user')
    set({ user: null, token: null })
  },
}))
