import { lazy, Suspense, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { RequireAuth } from '@mabi/shared/components/RequireAuth'
import Sidebar from './components/Sidebar'
import SearchPage from './pages/search'
import Marketplace from './pages/marketplace'
import Sell from './pages/sell'

const LoginPage = lazy(() => import('./pages/login'))

function App() {
  const { t } = useTranslation()
  useEffect(() => { document.title = t('app.title') }, [t])

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/market" element={<Marketplace />} />
          <Route path="/sell" element={<RequireAuth><Sell /></RequireAuth>} />
          <Route path="/login" element={<Suspense fallback=""><LoginPage /></Suspense>} />
          <Route path="*" element={<h1>404 Not Found</h1>} />
        </Routes>
      </main>
    </div>
  )
}

export default App
