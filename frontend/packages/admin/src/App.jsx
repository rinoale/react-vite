import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { OnboardingModal } from '@mabi/shared/components/OnboardingModal'
import { useAuth } from '@mabi/shared/hooks/useAuth'
import AdminLayout from './layouts/AdminLayout'

const EnchantPanel = lazy(() => import('./components/EnchantPanel'))
const EffectsPanel = lazy(() => import('./components/EffectsPanel'))
const ReforgeOptionsPanel = lazy(() => import('./components/ReforgeOptionsPanel'))
const EchostoneOptionsPanel = lazy(() => import('./components/EchostoneOptionsPanel'))
const MuriasRelicOptionsPanel = lazy(() => import('./components/MuriasRelicOptionsPanel'))
const GameItemsPanel = lazy(() => import('./components/GameItemsPanel'))
const ListingsPanel = lazy(() => import('./components/ListingsPanel'))
const CorrectionsPanel = lazy(() => import('./components/CorrectionsPanel'))
const TagsPanel = lazy(() => import('./components/TagsPanel'))
const JobsPanel = lazy(() => import('./components/JobsPanel'))
const UsersPanel = lazy(() => import('./components/UsersPanel'))
const RolesPanel = lazy(() => import('./components/RolesPanel'))
const FeatureFlagsPanel = lazy(() => import('./components/FeatureFlagsPanel'))
const UsagePanel = lazy(() => import('./components/UsagePanel'))
const ActivityLogsPanel = lazy(() => import('./components/ActivityLogsPanel'))

const Fallback = () => (
  <div className="flex items-center justify-center py-20">
    <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
  </div>
)

function AdminGuard({ children }) {
  const { user, isAuthenticated, loading } = useAuth()

  if (loading) return <Fallback />

  if (!isAuthenticated) {
    window.location.href = '/login'
    return null
  }

  const hasAccess = user?.roles?.includes('admin') || user?.roles?.includes('master')
  if (!hasAccess) {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col items-center justify-center gap-2">
        <p className="text-lg font-semibold text-gray-400">Unauthorized</p>
        <p className="text-sm text-gray-600">Admin access required.</p>
      </div>
    )
  }

  return children
}

function App() {
  const { t } = useTranslation()
  useEffect(() => { document.title = t('app.title') }, [t])

  return (
    <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/+$/, '')}>
      <AdminGuard>
      <Routes>
        <Route element={<AdminLayout />}>
          {/* Source of Truth */}
          <Route path="/source_of_truth" element={<Navigate to="/source_of_truth/enchants" replace />} />
          <Route path="/source_of_truth/enchants" element={<Suspense fallback={<Fallback />}><EnchantPanel /></Suspense>} />
          <Route path="/source_of_truth/effects" element={<Suspense fallback={<Fallback />}><EffectsPanel /></Suspense>} />
          <Route path="/source_of_truth/reforge_options" element={<Suspense fallback={<Fallback />}><ReforgeOptionsPanel /></Suspense>} />
          <Route path="/source_of_truth/echostone_options" element={<Suspense fallback={<Fallback />}><EchostoneOptionsPanel /></Suspense>} />
          <Route path="/source_of_truth/murias_relic_options" element={<Suspense fallback={<Fallback />}><MuriasRelicOptionsPanel /></Suspense>} />
          <Route path="/source_of_truth/game_items" element={<Suspense fallback={<Fallback />}><GameItemsPanel /></Suspense>} />

          {/* Trade */}
          <Route path="/trade" element={<Navigate to="/trade/listings" replace />} />
          <Route path="/trade/listings" element={<Suspense fallback={<Fallback />}><ListingsPanel /></Suspense>} />
          <Route path="/trade/corrections" element={<Suspense fallback={<Fallback />}><CorrectionsPanel /></Suspense>} />
          <Route path="/trade/tags" element={<Suspense fallback={<Fallback />}><TagsPanel /></Suspense>} />

          {/* System */}
          <Route path="/system" element={<Navigate to="/system/jobs" replace />} />
          <Route path="/system/jobs" element={<Suspense fallback={<Fallback />}><JobsPanel /></Suspense>} />
          <Route path="/system/users" element={<Suspense fallback={<Fallback />}><UsersPanel /></Suspense>} />
          <Route path="/system/roles" element={<Suspense fallback={<Fallback />}><RolesPanel /></Suspense>} />
          <Route path="/system/feature_flags" element={<Suspense fallback={<Fallback />}><FeatureFlagsPanel /></Suspense>} />
          <Route path="/system/usage" element={<Suspense fallback={<Fallback />}><UsagePanel /></Suspense>} />
          <Route path="/system/activity_logs" element={<Suspense fallback={<Fallback />}><ActivityLogsPanel /></Suspense>} />

          {/* Default */}
          <Route path="/" element={null} />
          {/* Legacy redirects */}
          <Route path="/enchants" element={<Navigate to="/source_of_truth/enchants" replace />} />
          <Route path="/listings" element={<Navigate to="/trade/listings" replace />} />
          <Route path="/corrections" element={<Navigate to="/trade/corrections" replace />} />
          <Route path="/tags" element={<Navigate to="/trade/tags" replace />} />
          <Route path="/jobs" element={<Navigate to="/system/jobs" replace />} />
          <Route path="/users" element={<Navigate to="/system/users" replace />} />
        </Route>
      </Routes>
      <OnboardingModal />
      </AdminGuard>
    </BrowserRouter>
  )
}

export default App
