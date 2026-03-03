import { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Sidebar from './components/Sidebar'
import SearchPage from './pages/search'
import Marketplace from './pages/marketplace'
import Sell from './pages/sell'

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
          <Route path="/sell" element={<Sell />} />
          <Route path="*" element={<h1>404 Not Found</h1>} />
        </Routes>
      </main>
    </div>
  )
}

export default App
