import { useMemo, useState, useEffect } from 'react';
import { Outlet, useLocation, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronRight, Database, ShoppingCart, Settings } from 'lucide-react';
import { useAuth } from '@mabi/shared/hooks/useAuth';
import { getSummary } from '@mabi/shared/api/admin';

const NAV_GROUPS = [
  {
    key: 'source_of_truth',
    icon: Database,
    items: [
      { key: 'enchants' },
      { key: 'effects' },
      { key: 'reforge_options' },
      { key: 'echostone_options' },
      { key: 'murias_relic_options' },
      { key: 'game_items' },
    ],
  },
  {
    key: 'trade',
    icon: ShoppingCart,
    items: [
      { key: 'listings' },
      { key: 'corrections' },
      { key: 'tags' },
    ],
  },
  {
    key: 'system',
    icon: Settings,
    items: [
      { key: 'jobs' },
      { key: 'users' },
      { key: 'roles' },
      { key: 'feature_flags' },
    ],
  },
];

const SUMMARY_KEYS = {
  enchants: 'enchants',
  effects: 'effects',
  reforge_options: 'reforge_options',
  echostone_options: 'echostone_options',
  murias_relic_options: 'murias_relic_options',
  game_items: 'game_items',
  listings: 'listings',
  tags: 'tags',
};

const AdminLayout = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isMaster = user?.roles?.includes('master');
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    getSummary().then((res) => setSummary(res.data)).catch(() => {});
  }, []);

  const activeGroup = useMemo(() => {
    const path = location.pathname;
    for (const g of NAV_GROUPS) {
      if (path.startsWith(`/${g.key}`)) return g.key;
    }
    return null;
  }, [location.pathname]);

  const activeItem = useMemo(() => {
    const parts = location.pathname.split('/');
    return parts.length >= 3 ? parts[2] : null;
  }, [location.pathname]);

  const visibleGroups = useMemo(() => {
    if (isMaster) return NAV_GROUPS;
    return NAV_GROUPS.map((g) => {
      if (g.key !== 'system') return g;
      return { ...g, items: g.items.filter((i) => i.key === 'jobs') };
    });
  }, [isMaster]);

  const handleGroupClick = (groupKey) => {
    navigate(`/${groupKey}`);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex">
      {/* sidebar */}
      <nav className="w-56 flex-shrink-0 bg-gray-950 border-r border-gray-800 flex flex-col">
        <div className="px-4 py-5 border-b border-gray-800">
          <h1 className="text-lg font-black text-white tracking-tight uppercase">
            {t('admin.title')} <span className="text-cyan-500">{t('admin.titleHighlight')}</span>
          </h1>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {visibleGroups.map((group) => {
            const isOpen = activeGroup === group.key;
            const Icon = group.icon;
            return (
              <div key={group.key}>
                {/* group-header */}
                <button
                  onClick={() => handleGroupClick(group.key)}
                  className={`w-full flex items-center gap-2 px-4 py-2.5 text-xs font-bold uppercase tracking-wider transition-colors ${
                    isOpen
                      ? 'text-cyan-400 bg-gray-900/50'
                      : 'text-gray-500 hover:text-gray-300 hover:bg-gray-900/30'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="flex-1 text-left">{t(`nav.${group.key}`)}</span>
                  {isOpen
                    ? <ChevronDown className="w-3 h-3" />
                    : <ChevronRight className="w-3 h-3" />}
                </button>

                {/* group-items */}
                {isOpen && (
                  <div className="pb-1">
                    {group.items.map((item) => {
                      const isActive = activeItem === item.key;
                      const count = summary?.[SUMMARY_KEYS[item.key]];
                      return (
                        <Link
                          key={item.key}
                          to={`/${group.key}/${item.key}`}
                          className={`flex items-center justify-between pl-10 pr-4 py-1.5 text-xs transition-colors ${
                            isActive
                              ? 'text-cyan-300 bg-cyan-900/20 border-r-2 border-cyan-400'
                              : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                          }`}
                        >
                          <span>{t(`nav.items.${item.key}`)}</span>
                          {count != null && (
                            <span className="text-[10px] font-mono text-gray-600">{count.toLocaleString()}</span>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </nav>

      {/* content */}
      <main className="flex-1 p-6 overflow-auto">
        <div className="max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default AdminLayout;
