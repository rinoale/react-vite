import { StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { initI18n } from '@mabi/shared/i18n'
import { AuthProvider } from '@mabi/shared/components/AuthProvider'
import { ToastProvider } from '@mabi/shared/components/ToastProvider'
import './index.css'
import App from './App.jsx'

initI18n()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Suspense fallback="">
      <ToastProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ToastProvider>
    </Suspense>
  </StrictMode>,
)
