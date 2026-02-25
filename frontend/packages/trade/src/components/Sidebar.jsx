import { Link, useLocation } from 'react-router-dom'
import { ShoppingBag, Upload } from 'lucide-react'

function NavLink({ to, icon: Icon, children }) {
  const { pathname } = useLocation()
  const active = pathname === to
  return (
    <Link
      to={to}
      className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-gray-700 text-white'
          : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200'
      }`}
    >
      <Icon className="w-5 h-5 shrink-0" />
      <span>{children}</span>
    </Link>
  )
}

const Sidebar = () => (
  <nav className="w-56 shrink-0 bg-gray-800 border-r border-gray-700 flex flex-col p-4 gap-1">
    <Link to="/" className="mb-6 px-2 flex items-center gap-3 hover:opacity-80 transition-opacity" title="Home">
      <img src="/favicon.svg" alt="Home" className="w-8 h-8" />
      <span className="text-white font-black text-lg tracking-tight">MABI</span>
    </Link>
    <NavLink to="/" icon={ShoppingBag}>Marketplace</NavLink>
    <NavLink to="/sell" icon={Upload}>Sell Item</NavLink>
  </nav>
)

export default Sidebar
