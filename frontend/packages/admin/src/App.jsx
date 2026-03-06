import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { OnboardingModal } from '@mabi/shared/components/OnboardingModal'
import Admin from './pages/admin'

function App() {
  const { t } = useTranslation()
  useEffect(() => { document.title = t('app.title') }, [t])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/:tab" element={<Admin />} />
        <Route path="/" element={<Admin />} />
      </Routes>
      <OnboardingModal />
    </BrowserRouter>
  )
}

export default App
