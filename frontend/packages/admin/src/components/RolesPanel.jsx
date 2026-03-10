import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, RefreshCw, ShieldCheck, Plus } from 'lucide-react';
import {
  getRoles, getFeatureFlags,
  assignFeatureToRole, removeFeatureFromRole,
} from '@mabi/shared/api/admin';

const panelWrapper = 'bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden';
const panelHeader = 'bg-gray-700/50 px-6 py-4 flex justify-between items-center';
const panelTitle = 'text-xl font-bold flex items-center gap-2';
const sectionCard = 'bg-gray-900/50 rounded-lg border border-gray-700 p-4';
const featureBadge = 'text-xs px-2 py-0.5 rounded border cursor-pointer select-none transition-colors';
const featureBadgeActive = 'bg-emerald-900/50 text-emerald-300 border-emerald-700/50 hover:bg-emerald-800/50';
const featureBadgeInactive = 'bg-gray-800 text-gray-500 border-gray-600 hover:bg-gray-700';

const RolesPanel = () => {
  const { t } = useTranslation();
  const [roles, setRoles] = useState([]);
  const [featureFlags, setFeatureFlags] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [togglingFeature, setTogglingFeature] = useState({});

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [rolesRes, flagsRes] = await Promise.all([
        getRoles(),
        getFeatureFlags(),
      ]);
      setRoles(rolesRes.data || []);
      setFeatureFlags(flagsRes.data || []);
    } catch (error) {
      console.error('Error fetching roles data:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

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

  if (isLoading && roles.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="w-12 h-12 text-emerald-500 animate-spin mb-4" />
        <p className="text-gray-400 font-bold tracking-widest uppercase">{t('roles.loading')}</p>
      </div>
    );
  }

  return (
    <div className={panelWrapper}>
      <div className={panelHeader}>
        <h2 className={panelTitle}>
          <ShieldCheck className="w-5 h-5 text-emerald-500" />
          {t('users.rolesAndFeatures')}
        </h2>
        <button onClick={fetchData} className="p-1 hover:text-emerald-400" title={t('users.refresh')}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
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
        {roles.length === 0 && (
          <p className="text-center text-gray-500 py-8 col-span-full">{t('roles.noRoles')}</p>
        )}
      </div>
    </div>
  );
};

export default RolesPanel;
