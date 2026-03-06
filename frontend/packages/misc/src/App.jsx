import { useEffect } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Navigate from './pages/navigate'
import ImageProcess from './pages/image_process'
import ImageProcessLab from './pages/image_process_lab'
import V3PipelineViewer from './pages/v3_pipeline_viewer'
import HornBugle from './pages/horn_bugle'

function App() {
  const { t } = useTranslation()
  useEffect(() => { document.title = t('app.title') }, [t])

  return (
    <>
      <div>
        <nav className="p-4 bg-gray-800 text-white mb-4 rounded-lg flex gap-4 justify-center">
          <Link to="/navigate" className="hover:text-cyan-400">Navigate</Link> |{' '}
          <Link to="/image_process" className="hover:text-cyan-400">Image Process (Debug)</Link> |{' '}
          <Link to="/image_process_lab" className="hover:text-cyan-400">Image Process Lab</Link> |{' '}
          <Link to="/v3_pipeline" className="hover:text-cyan-400">V3 Pipeline</Link> |{' '}
          <Link to="/horn_bugle" className="hover:text-cyan-400">Horn Bugle</Link>
        </nav>
        <Routes>
          <Route path="/navigate" element={<Navigate />} />
          <Route path="/image_process" element={<ImageProcess />} />
          <Route path="/image_process_lab" element={<ImageProcessLab />} />
          <Route path="/v3_pipeline" element={<V3PipelineViewer />} />
          <Route path="/horn_bugle" element={<HornBugle />} />
          <Route path="*" element={<h1>404 Not Found</h1>} />
        </Routes>
      </div>
    </>
  )
}

export default App
