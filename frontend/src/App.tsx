import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RootLayout from '@/components/layout/RootLayout'
import Login from '@/routes/Login'
import RequestsList from '@/routes/RequestsList'
import RequestDetail from '@/routes/RequestDetail'
import Analytics from '@/routes/Analytics'
import Admin from '@/routes/Admin'
import { Toaster } from '@/components/shared/Toaster'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<RootLayout />}>
            <Route path="/" element={<RequestsList />} />
            <Route path="/requests/:id" element={<RequestDetail />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/admin" element={<Admin />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  )
}
