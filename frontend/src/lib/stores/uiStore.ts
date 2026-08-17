import { create } from 'zustand'
import { uid } from '@/lib/utils'

export interface Toast {
  id: string
  message: string
  kind: 'success' | 'error' | 'info'
}

interface UiState {
  toasts: Toast[]
  toast: (message: string, kind?: Toast['kind']) => void
  dismiss: (id: string) => void
}

export const useUiStore = create<UiState>((set) => ({
  toasts: [],
  toast: (message, kind = 'info') => {
    const id = uid('t_')
    set((s) => ({ toasts: [...s.toasts, { id, message, kind }] }))
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
    }, 4200)
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))
