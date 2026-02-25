import { Routes, Route, Link } from 'react-router-dom'
import Navigate from './pages/navigate'
import ImageProcess from './pages/image_process'

function App() {
  return (
    <>
      <div>
        <nav className="p-4 bg-gray-800 text-white mb-4 rounded-lg flex gap-4 justify-center">
          <Link to="/navigate" className="hover:text-cyan-400">Navigate</Link> |{' '}
          <Link to="/image_process" className="hover:text-cyan-400">Image Process (Debug)</Link>
        </nav>
        <Routes>
          <Route path="/navigate" element={<Navigate />} />
          <Route path="/image_process" element={<ImageProcess />} />
          <Route path="*" element={<h1>404 Not Found</h1>} />
        </Routes>
      </div>
    </>
  )
}

export default App
