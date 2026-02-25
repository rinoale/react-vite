import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Marketplace from './pages/marketplace'
import Sell from './pages/sell'

function App() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Marketplace />} />
          <Route path="/sell" element={<Sell />} />
          <Route path="*" element={<h1>404 Not Found</h1>} />
        </Routes>
      </main>
    </div>
  )
}

export default App
