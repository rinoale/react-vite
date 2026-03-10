import { useCallback, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Search, ShoppingBag, Upload, Package, LogIn, LogOut, Menu, ChevronsLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@mabi/shared/hooks/useAuth'
import PlayerName from '@mabi/shared/components/PlayerName'

const navLinkBase = 'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors';
const navLinkCollapsed = 'flex items-center justify-center p-2 rounded-lg text-sm font-medium transition-colors';
const navLinkActive = 'bg-gray-700 text-white';
const navLinkInactive = 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200';
const sidebarExpanded = 'w-56 shrink-0 bg-gray-800 border-r border-gray-700 flex flex-col p-4 gap-1 transition-all duration-200';
const sidebarCollapsed = 'w-14 shrink-0 bg-gray-800 border-r border-gray-700 flex flex-col p-2 gap-1 items-center transition-all duration-200';
const sidebarLogo = 'mb-6 px-2 flex items-center gap-3 hover:opacity-80 transition-opacity';
const sidebarLogoCollapsed = 'mb-6 flex justify-center hover:opacity-80 transition-opacity';
const userInfoBox = 'mt-auto px-3 py-2 text-sm text-gray-400 border-t border-gray-700';
const userInfoBoxCollapsed = 'mt-auto py-2 text-sm text-gray-400 border-t border-gray-700 flex justify-center';
const userName = 'truncate text-gray-300 text-xs';
const logoutBtn = 'flex items-center gap-2 text-sm text-gray-400 hover:text-red-400 transition-colors cursor-pointer mt-1';
const toggleBtn = 'p-1.5 rounded-lg text-gray-400 hover:bg-gray-700/50 hover:text-gray-200 transition-colors';

function NavLink({ to, icon: Icon, children, collapsed }) {
  const { pathname } = useLocation()
  const active = pathname === to
  const base = collapsed ? navLinkCollapsed : navLinkBase
  const variant = active ? navLinkActive : navLinkInactive
  return (
    <Link to={to} className={`${base} ${variant}`} title={collapsed ? children : undefined}>
      <Icon className="w-5 h-5 shrink-0" />
      {!collapsed && <span>{children}</span>}
    </Link>
  )
}

const Sidebar = () => {
  const { t } = useTranslation()
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const handleLogout = useCallback(async () => {
    await logout()
    navigate('/')
  }, [logout, navigate])

  const handleToggle = useCallback(() => {
    setCollapsed(prev => !prev)
  }, [])

  return (
    <nav className={collapsed ? sidebarCollapsed : sidebarExpanded}>
      {/* toggle + logo */}
      {collapsed ? (
        <>
          <button type="button" className={toggleBtn} onClick={handleToggle} title={t('sidebar.expand')}>
            <Menu className="w-5 h-5" />
          </button>
          <Link to="/" className={sidebarLogoCollapsed} title={t('sidebar.home')}>
            <img src="/favicon.svg" alt="Home" className="w-8 h-8" />
          </Link>
        </>
      ) : (
        <div className="flex items-center justify-between mb-6">
          <Link to="/" className="px-2 flex items-center gap-3 hover:opacity-80 transition-opacity" title="Home">
            <img src="/favicon.svg" alt="Home" className="w-8 h-8" />
            <span className="text-white font-black text-lg tracking-tight">{t('sidebar.home')}</span>
          </Link>
          <button type="button" className={toggleBtn} onClick={handleToggle} title={t('sidebar.collapse')}>
            <ChevronsLeft className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* nav-links */}
      <NavLink to="/" icon={Search} collapsed={collapsed}>{t('sidebar.search', 'Search')}</NavLink>
      <NavLink to="/market" icon={ShoppingBag} collapsed={collapsed}>{t('sidebar.marketplace')}</NavLink>
      <NavLink to="/sell" icon={Upload} collapsed={collapsed}>{t('sidebar.sellItem')}</NavLink>
      {isAuthenticated && (
        <NavLink to="/my-listings" icon={Package} collapsed={collapsed}>{t('sidebar.myListings')}</NavLink>
      )}

      {/* user-info */}
      <div className={collapsed ? userInfoBoxCollapsed : userInfoBox}>
        {isAuthenticated ? (
          collapsed ? (
            <button type="button" onClick={handleLogout} className={toggleBtn} title={t('auth.logout')}>
              <LogOut className="w-5 h-5 text-gray-400 hover:text-red-400" />
            </button>
          ) : (
            <>
              <PlayerName server={user?.server} gameId={user?.game_id} className={userName} copyable={false} />
              <button type="button" className={logoutBtn} onClick={handleLogout}>
                <LogOut className="w-4 h-4" />
                {t('auth.logout')}
              </button>
            </>
          )
        ) : (
          <NavLink to="/login" icon={LogIn} collapsed={collapsed}>{t('auth.loginTitle')}</NavLink>
        )}
      </div>
    </nav>
  )
}

export default Sidebar
