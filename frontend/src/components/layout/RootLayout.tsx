import { NavLink, Outlet, Navigate } from 'react-router-dom'
import { BarChart3, ClipboardList, Database, LogOut, ShieldCheck } from 'lucide-react'
import { useAuthStore } from '@/lib/stores/authStore'
import { cn } from '@/lib/utils'

const nav = [
  { to: '/', label: 'Заявки', icon: ClipboardList },
  { to: '/analytics', label: 'Аналитика', icon: BarChart3 },
  { to: '/admin', label: 'Админ', icon: Database, adminOnly: true },
]

export default function RootLayout() {
  const { user, logout } = useAuthStore()
  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="flex h-full">
      <aside className="flex w-14 shrink-0 flex-col md:w-60 bg-gradient-to-b from-brand-900 to-brand-950 text-white">
        <div className="flex items-center gap-3 px-3 py-6 md:px-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/20">
            <ShieldCheck className="h-5 w-5 text-brand-200" />
          </div>
          <div className="hidden md:block">
            <p className="text-base font-bold tracking-wide">ПРОСТОР 2.0</p>
            <p className="text-[11px] text-brand-200">конструктор ТЗ + ИИ-поиск</p>
          </div>
        </div>
        <nav className="mt-2 flex-1 space-y-1 px-2 md:px-3">
          {nav
            .filter((item) => !item.adminOnly || user.role === 'admin')
            .map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                title={item.label}
                className={({ isActive }) =>
                  cn(
                    'flex items-center justify-center gap-3 rounded-lg px-2 py-2.5 text-sm font-medium transition-colors md:justify-start md:px-3',
                    isActive ? 'bg-white text-brand-900 shadow-sm' : 'text-brand-100 hover:bg-white/10',
                  )
                }
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="hidden md:inline">{item.label}</span>
              </NavLink>
            ))}
        </nav>
        <div className="border-t border-white/10 p-2 md:p-4">
          <div className="mb-3 flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-700 text-sm font-bold">
              {user.username.slice(0, 2).toUpperCase()}
            </div>
            <div className="hidden min-w-0 md:block">
              <p className="truncate text-sm font-medium">{user.full_name}</p>
              <p className="text-[11px] text-brand-300">{user.role === 'admin' ? 'Администратор' : 'Заказчик'}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/20 px-3 py-2 text-sm text-brand-100 transition-colors hover:bg-white/10"
          >
            <LogOut className="h-4 w-4" />
            Выйти
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto bg-slate-50">
        <Outlet />
      </main>
    </div>
  )
}
