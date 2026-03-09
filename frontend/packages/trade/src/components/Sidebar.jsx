import { useCallback } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Search, ShoppingBag, Upload, LogIn, LogOut } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@mabi/shared/hooks/useAuth'
import PlayerName from '@mabi/shared/components/PlayerName'

const navLinkBase = 'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors';
const navLinkActive = `${navLinkBase} bg-gray-700 text-white`;
const navLinkInactive = `${navLinkBase} text-gray-400 hover:bg-gray-700/50 hover:text-gray-200`;
const sidebarNav = 'w-56 shrink-0 bg-gray-800 border-r border-gray-700 flex flex-col p-4 gap-1';
const sidebarLogo = 'mb-6 px-2 flex items-center gap-3 hover:opacity-80 transition-opacity';
const userInfoBox = 'mt-auto px-3 py-2 text-sm text-gray-400 border-t border-gray-700';
const userName = 'truncate text-gray-300 text-xs';
const logoutBtn = 'flex items-center gap-2 text-sm text-gray-400 hover:text-red-400 transition-colors cursor-pointer mt-1';

function NavLink({ to, icon: Icon, children }) {
  const { pathname } = useLocation()
  const active = pathname === to
  return (
    <Link to={to} className={active ? navLinkActive : navLinkInactive}>
      <Icon className="w-5 h-5 shrink-0" />
      <span>{children}</span>
    </Link>
  )
}

const Sidebar = () => {
  const { t } = useTranslation()
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = useCallback(async () => {
    await logout()
    navigate('/')
  }, [logout, navigate])

  return (
    <nav className={sidebarNav}>
      <Link to="/" className={sidebarLogo} title="Home">
        <img src="/favicon.svg" alt="Home" className="w-8 h-8" />
        <span className="text-white font-black text-lg tracking-tight">{t('sidebar.home')}</span>
      </Link>
      <NavLink to="/" icon={Search}>{t('sidebar.search', 'Search')}</NavLink>
      <NavLink to="/market" icon={ShoppingBag}>{t('sidebar.marketplace')}</NavLink>
      <NavLink to="/sell" icon={Upload}>{t('sidebar.sellItem')}</NavLink>

      <div className={userInfoBox}>
        {isAuthenticated ? (
          <>
            <PlayerName server={user?.server} gameId={user?.game_id} className={userName} />
            <button type="button" className={logoutBtn} onClick={handleLogout}>
              <LogOut className="w-4 h-4" />
              {t('auth.logout')}
            </button>
          </>
        ) : (
          <NavLink to="/login" icon={LogIn}>{t('auth.loginTitle')}</NavLink>
        )}
      </div>
    </nav>
  )
}

export default Sidebar
