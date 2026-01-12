import { useState } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

import ImageProcess from './pages/image_process'
import Navigate from './pages/navigate'

function App() {
  return (
    <>
      <div>
        <Routes>
          <Route path="/navigate" element={<Navigate />} />
          <Route path="/image_process" element={<ImageProcess />} />
          {/* Optional: Add a catch-all route for 404 pages */}
          <Route path="*" element={<h1>404 Not Found</h1>} />
        </Routes>
        <nav>
          <Link to="/">Home</Link> |{' '}
          <Link to="/navigate">navigate</Link> |{' '}
          <Link to="/image_process">Image Process</Link>
        </nav>
      </div>
    </>
  )
}

export default App
