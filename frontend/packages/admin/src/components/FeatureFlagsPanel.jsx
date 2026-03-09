import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, RefreshCw, Flag } from 'lucide-react';
import { getFeatureFlags, getRoles } from '@mabi/shared/api/admin';

const panelWrapper = 'bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden';
const panelHeader = 'bg-gray-700/50 px-6 py-4 flex justify-between items-center';
const panelTitle = 'text-xl font-bold flex items-center gap-2';
const tableHeader = 'text-left text-[10px] font-black text-gray-500 uppercase px-3 py-2';
const tableCell = 'px-3 py-2 text-sm';

const FeatureFlagsPanel = () => {
  const { t } = useTranslation();
  const [featureFlags, setFeatureFlags] = useState([]);
  const [roles, setRoles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [flagsRes, rolesRes] = await Promise.all([
        getFeatureFlags(),
        getRoles(),
      ]);
      setFeatureFlags(flagsRes.data || []);
      setRoles(rolesRes.data || []);
    } catch (error) {
      console.error('Error fetching feature flags data:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const getRolesForFlag = useCallback((flagName) => {
    return roles.filter((role) => role.features.includes(flagName));
  }, [roles]);

  if (isLoading && featureFlags.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Loader2 className="w-12 h-12 text-amber-500 animate-spin mb-4" />
        <p className="text-gray-400 font-bold tracking-widest uppercase">{t('featureFlags.loading')}</p>
      </div>
    );
  }

  return (
    <div className={panelWrapper}>
      <div className={panelHeader}>
        <h2 className={panelTitle}>
          <Flag className="w-5 h-5 text-amber-500" />
          {t('featureFlags.title')}
        </h2>
        <button onClick={fetchData} className="p-1 hover:text-amber-400" title={t('featureFlags.refresh')}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-700">
              <th className={tableHeader}>ID</th>
              <th className={tableHeader}>{t('featureFlags.name')}</th>
              <th className={tableHeader}>{t('featureFlags.assignedRoles')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {featureFlags.map((flag) => {
              const assignedRoles = getRolesForFlag(flag.name);
              return (
                <tr key={flag.id} className="hover:bg-gray-700/30">
                  <td className={`${tableCell} text-gray-500 font-mono`}>{flag.id}</td>
                  <td className={`${tableCell} text-gray-200 font-medium`}>{flag.name}</td>
                  <td className={tableCell}>
                    <div className="flex flex-wrap gap-1">
                      {assignedRoles.length > 0 ? (
                        assignedRoles.map((role) => (
                          <span
                            key={role.id}
                            className="text-xs px-2 py-0.5 rounded bg-cyan-900/50 text-cyan-300 border border-cyan-700/50"
                          >
                            {role.name}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-gray-500">{t('featureFlags.noRoles')}</span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {featureFlags.length === 0 && (
          <p className="text-center text-gray-500 py-8">{t('featureFlags.noFlags')}</p>
        )}
      </div>
    </div>
  );
};

export default FeatureFlagsPanel;
