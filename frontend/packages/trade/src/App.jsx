import { Routes, Route, Link } from 'react-router-dom'
import Marketplace from './pages/marketplace'
import Sell from './pages/sell'

function App() {
  return (
    <>
      <div>
        <nav className="p-4 bg-gray-800 text-white mb-4 rounded-lg flex gap-4 justify-center">
          <Link to="/" className="hover:text-cyan-400 font-bold">Marketplace</Link> |{' '}
          <Link to="/sell" className="hover:text-cyan-400 font-bold text-cyan-300">Sell Item</Link>
        </nav>
        <Routes>
          <Route path="/" element={<Marketplace />} />
          <Route path="/sell" element={<Sell />} />
          <Route path="*" element={<h1>404 Not Found</h1>} />
        </Routes>
      </div>
    </>
  )
}

export default App
