import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, RefreshCw, Shield, ShieldCheck, ShieldX, Plus, X } from 'lucide-react';
import {
  getUsers, getRoles, getFeatureFlags,
  assignRole, removeRole,
  assignFeatureToRole, removeFeatureFromRole,
} from '@mabi/shared/api/admin';

const panelWrapper = 'bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden';
const panelHeader = 'bg-gray-700/50 px-6 py-4 flex justify-between items-center';
const panelTitle = 'text-xl font-bold flex items-center gap-2';
const sectionTitle = 'text-lg font-bold text-white mb-3';
const sectionCard = 'bg-gray-900/50 rounded-lg border border-gray-700 p-4';
const roleBadge = 'text-xs px-2 py-0.5 rounded border cursor-pointer select-none transition-colors';
const roleBadgeActive = 'bg-cyan-900/50 text-cyan-300 border-cyan-700/50 hover:bg-cyan-800/50';
const roleBadgeInactive = 'bg-gray-800 text-gray-500 border-gray-600 hover:bg-gray-700';
const featureBadge = 'text-xs px-2 py-0.5 rounded border cursor-pointer select-none transition-colors';
const featureBadgeActive = 'bg-emerald-900/50 text-emerald-300 border-emerald-700/50 hover:bg-emerald-800/50';
const featureBadgeInactive = 'bg-gray-800 text-gray-500 border-gray-600 hover:bg-gray-700';
const tableHeader = 'text-left text-[10px] font-black text-gray-500 uppercase px-3 py-2';
const tableCell = 'px-3 py-2 text-sm';
const paginationBtn = 'text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded';

const UsersPanel = () => {
  const { t } = useTranslation();
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [featureFlags, setFeatureFlags] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });
  const [togglingRole, setTogglingRole] = useState({});
  const [togglingFeature, setTogglingFeature] = useState({});

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [usersRes, rolesRes, flagsRes] = await Promise.all([
        getUsers({ limit: pagination.limit, offset: pagination.offset }),
        getRoles(),
        getFeatureFlags(),
      ]);
      setUsers(usersRes.data.rows || []);
      setRoles(rolesRes.data || []);
      setFeatureFlags(flagsRes.data || []);
    } catch (error) {
      console.error('Error fetching user management data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.offset, pagination.limit]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleToggleRole = useCallback(async (userId, roleName, hasRole) => {
    const key = `${userId}-${roleName}`;
    setTogglingRole((prev) => ({ ...prev, [key]: true }));
    try {
      if (hasRole) {
        await removeRole(userId, roleName);
      } else {
        await assignRole(userId, roleName);
      }
      setUsers((prev) => prev.map((u) => {
        if (u.id !== userId) return u;
        const newRoles = hasRole
          ? u.roles.filter((r) => r !== roleName)
          : [...u.roles, roleName];
        return { ...u, roles: newRoles };
      }));
    } catch (error) {
      console.error('Error toggling role:', error);
    } finally {
      setTogglingRole((prev) => ({ ...prev, [key]: false }));
    }
  }, []);

  const handleToggleFeature = useCallback(async (roleName, flagName, hasFeature) => {
    const key = `${roleName}-${flagName}`;
    setTogglingFeature((prev) => ({ ...prev, [key]: true }));
    try {
      if (hasFeature) {
        await removeFeatureFromRole(roleName, flagName);
      } else {
        await assignFeatureToRole(roleName, flagName);
      }
      setRoles((prev) => prev.map((r) => {
        if (r.name !== roleName) return r;
        const newFeatures = hasFeature
          ? r.features.filter((f) => f !== flagName)
          : [...r.features, flagName];
        return { ...r, features: newFeatures };
      }));
    } catch (error) {
      console.error('Error toggling feature:', error);
    } finally {
      setTogglingFeature((prev) => ({ ...prev, [key]: false }));
    }
  }, []);

  const handlePrev = useCallback(() => {
    setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }));
  }, []);

  const handleNext = useCallback(() => {
    setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }));
  }, []);

  if (isLoading && users.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mb-4" />
        <p className="text-gray-400 font-bold tracking-widest uppercase">{t('users.loading')}</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6">
      {/* Roles & Feature Flags */}
      <div className={panelWrapper}>
        <div className={panelHeader}>
          <h2 className={panelTitle}>
            <ShieldCheck className="w-5 h-5 text-emerald-500" />
            {t('users.rolesAndFeatures')}
          </h2>
        </div>
        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
          {roles.map((role) => (
            <div key={role.id} className={sectionCard}>
              <h3 className="text-sm font-bold text-cyan-400 mb-2 uppercase">{role.name}</h3>
              <div className="flex flex-wrap gap-1.5">
                {featureFlags.map((flag) => {
                  const hasFeature = role.features.includes(flag.name);
                  const key = `${role.name}-${flag.name}`;
                  const isToggling = !!togglingFeature[key];
                  return (
                    <button
                      key={flag.id}
                      className={`${featureBadge} ${hasFeature ? featureBadgeActive : featureBadgeInactive}`}
                      onClick={() => handleToggleFeature(role.name, flag.name, hasFeature)}
                      disabled={isToggling}
                    >
                      {isToggling ? <Loader2 className="w-3 h-3 animate-spin inline mr-1" /> : null}
                      {hasFeature ? <Plus className="w-3 h-3 inline mr-0.5 rotate-45" /> : <Plus className="w-3 h-3 inline mr-0.5" />}
                      {flag.name}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* User List */}
      <div className={panelWrapper}>
        <div className={panelHeader}>
          <h2 className={panelTitle}>
            <Shield className="w-5 h-5 text-cyan-500" />
            {t('users.title')}
          </h2>
          <div className="flex items-center gap-4">
            <button onClick={handlePrev} className={paginationBtn} disabled={pagination.offset === 0}>
              {t('users.prev')}
            </button>
            <span className="text-xs font-mono">
              {pagination.offset + 1} - {pagination.offset + users.length}
            </span>
            <button onClick={handleNext} className={paginationBtn} disabled={users.length < pagination.limit}>
              {t('users.next')}
            </button>
            <button onClick={fetchData} className="p-1 hover:text-cyan-400" title={t('users.refresh')}>
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className={tableHeader}>ID</th>
                <th className={tableHeader}>{t('users.email')}</th>
                <th className={tableHeader}>{t('users.discord')}</th>
                <th className={tableHeader}>{t('users.server')}</th>
                <th className={tableHeader}>{t('users.gameId')}</th>
                <th className={tableHeader}>{t('users.status')}</th>
                <th className={tableHeader}>{t('users.roles')}</th>
                <th className={tableHeader}>{t('users.createdAt')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700/50">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-gray-700/30">
                  <td className={`${tableCell} text-gray-500 font-mono`}>{user.id}</td>
                  <td className={`${tableCell} text-gray-200`}>{user.email}</td>
                  <td className={`${tableCell} text-indigo-300`}>{user.discord_username || '-'}</td>
                  <td className={`${tableCell} text-gray-400`}>{user.server || '-'}</td>
                  <td className={`${tableCell} text-gray-400`}>{user.game_id || '-'}</td>
                  <td className={tableCell}>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${user.status === 0 ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>
                      {user.status === 0 ? t('users.active') : t('users.inactive')}
                    </span>
                  </td>
                  <td className={tableCell}>
                    <div className="flex flex-wrap gap-1">
                      {roles.map((role) => {
                        const hasRole = user.roles?.includes(role.name);
                        const key = `${user.id}-${role.name}`;
                        const isToggling = !!togglingRole[key];
                        return (
                          <button
                            key={role.id}
                            className={`${roleBadge} ${hasRole ? roleBadgeActive : roleBadgeInactive}`}
                            onClick={() => handleToggleRole(user.id, role.name, hasRole)}
                            disabled={isToggling}
                          >
                            {isToggling ? <Loader2 className="w-3 h-3 animate-spin inline mr-0.5" /> : null}
                            {role.name}
                          </button>
                        );
                      })}
                    </div>
                  </td>
                  <td className={`${tableCell} text-gray-500 text-xs`}>
                    {user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && (
            <p className="text-center text-gray-500 py-8">{t('users.noUsers')}</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default UsersPanel;
