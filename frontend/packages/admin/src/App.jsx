import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import Admin from './pages/admin'

function App() {
  const { t } = useTranslation()
  useEffect(() => { document.title = t('app.title') }, [t])

  return <Admin />
}

export default App
