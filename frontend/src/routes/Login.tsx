import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/controls'
import { useAuthStore } from '@/lib/stores/authStore'

export default function Login() {
  const [username, setUsername] = useState('demo')
  const [loading, setLoading] = useState(false)
  const login = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim()) return
    setLoading(true)
    try {
      await login(username.trim())
      navigate('/', { replace: true })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center bg-gradient-to-br from-brand-950 via-brand-900 to-brand-800 p-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-modal">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-800 text-white">
            <ShieldCheck className="h-7 w-7" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">ПРОСТОР 2.0</h1>
            <p className="mt-1 text-sm text-slate-500">Умный конструктор ТЗ + ИИ-агент умного поиска</p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="username">Логин</Label>
            <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="например, demo" autoFocus />
          </div>
          <Button type="submit" className="w-full" loading={loading}>
            Войти
          </Button>
          <p className="text-center text-xs text-slate-400">
            Демо-режим: любой логин подходит, «admin» — роль администратора
          </p>
        </form>
      </div>
    </div>
  )
}
