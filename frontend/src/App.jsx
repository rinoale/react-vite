import { useState } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

import ImageProcess from './pages/image_process'
import Navigate from './pages/navigate'
import Sell from './pages/sell'
import Marketplace from './pages/marketplace'
import Admin from './pages/admin'

function App() {
  return (
    <>
      <div>
        <nav className="p-4 bg-gray-800 text-white mb-4 rounded-lg flex gap-4 justify-center">
          <Link to="/" className="hover:text-cyan-400 font-bold">Marketplace</Link> |{' '}
          <Link to="/sell" className="hover:text-cyan-400 font-bold text-cyan-300">Sell Item</Link> |{' '}
          <Link to="/admin" className="hover:text-cyan-400 font-bold">Admin</Link> |{' '}
          <Link to="/navigate" className="hover:text-cyan-400">Navigate</Link> |{' '}
          <Link to="/image_process" className="hover:text-cyan-400">Image Process (Debug)</Link>
        </nav>
        <Routes>
          <Route path="/" element={<Marketplace />} />
          <Route path="/navigate" element={<Navigate />} />
          <Route path="/image_process" element={<ImageProcess />} />
          <Route path="/sell" element={<Sell />} />
          <Route path="/admin" element={<Admin />} />
          {/* Optional: Add a catch-all route for 404 pages */}
          <Route path="*" element={<h1>404 Not Found</h1>} />
        </Routes>
      </div>
    </>
  )
}

export default App
