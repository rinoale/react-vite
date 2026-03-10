import { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getR2Usage, getOciUsage } from '@mabi/shared/api/admin';
import {
  panelOuter, panelHeader, panelTitle, loadingCenter, loadingIcon,
} from '@mabi/shared/styles';

const formatNumber = (n) => n.toLocaleString();

const formatBytes = (bytes) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
};

const formatCost = (n) => `$${n.toFixed(4)}`;

const barColor = (pct) => {
  if (pct >= 90) return 'bg-red-500';
  if (pct >= 70) return 'bg-amber-500';
  return 'bg-cyan-500';
};

const UsageBar = ({ label, used, limit, pct, formatFn = formatNumber }) => (
  <div className="space-y-1">
    <div className="flex justify-between text-sm">
      <span className="text-gray-300">{label}</span>
      <span className="text-gray-400 font-mono text-xs">
        {formatFn(used)} / {formatFn(limit)} ({pct}%)
      </span>
    </div>
    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${barColor(pct)}`}
        style={{ width: `${Math.min(pct, 100)}%` }}
      />
    </div>
  </div>
);

const RefreshBtn = ({ onClick, isLoading, title }) => (
  <button onClick={onClick} className="p-1 hover:text-cyan-400" title={title}>
    <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
  </button>
);

const UsagePanel = () => {
  const { t } = useTranslation();

  /* --- R2 state --- */
  const [r2, setR2] = useState(null);
  const [r2Loading, setR2Loading] = useState(true);
  const [r2Error, setR2Error] = useState(null);

  /* --- OCI state --- */
  const [oci, setOci] = useState(null);
  const [ociLoading, setOciLoading] = useState(true);
  const [ociError, setOciError] = useState(null);

  const fetchR2 = useCallback(async () => {
    setR2Loading(true);
    setR2Error(null);
    try {
      const res = await getR2Usage();
      setR2(res.data);
    } catch (err) {
      setR2Error(err.response?.data?.detail || err.message);
    } finally {
      setR2Loading(false);
    }
  }, []);

  const fetchOci = useCallback(async () => {
    setOciLoading(true);
    setOciError(null);
    try {
      const res = await getOciUsage();
      setOci(res.data);
    } catch (err) {
      setOciError(err.response?.data?.detail || err.message);
    } finally {
      setOciLoading(false);
    }
  }, []);

  useEffect(() => { fetchR2(); }, [fetchR2]);
  useEffect(() => { fetchOci(); }, [fetchOci]);

  const initialLoading = (r2Loading && !r2) && (ociLoading && !oci);
  if (initialLoading) {
    return (
      <div className={loadingCenter}>
        <Loader2 className={loadingIcon} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* R2 panel */}
      <div className={panelOuter}>
        <div className={panelHeader}>
          <h2 className={panelTitle}>{t('usage.r2Title')}</h2>
          <div className="flex items-center gap-3">
            {r2?.period && (
              <span className="text-xs text-gray-500 font-mono">{r2.period}</span>
            )}
            <RefreshBtn onClick={fetchR2} isLoading={r2Loading} title={t('usage.refresh')} />
          </div>
        </div>

        {r2Error ? (
          <div className="px-4 py-6 text-sm text-red-400">{r2Error}</div>
        ) : r2 ? (
          <div className="p-4 space-y-4">
            <UsageBar
              label={t('usage.storage')}
              used={r2.storage.used_bytes}
              limit={r2.storage.limit_gb * 1024 ** 3}
              pct={r2.storage.pct}
              formatFn={formatBytes}
            />
            <UsageBar
              label={t('usage.classA')}
              used={r2.class_a_ops.used}
              limit={r2.class_a_ops.limit}
              pct={r2.class_a_ops.pct}
            />
            <UsageBar
              label={t('usage.classB')}
              used={r2.class_b_ops.used}
              limit={r2.class_b_ops.limit}
              pct={r2.class_b_ops.pct}
            />
            {r2.storage.objects != null && (
              <div className="text-xs text-gray-500 pt-1">
                {t('usage.objects')}: {formatNumber(r2.storage.objects)}
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* OCI panel */}
      <div className={panelOuter}>
        <div className={panelHeader}>
          <h2 className={panelTitle}>{t('usage.ociTitle')}</h2>
          <div className="flex items-center gap-3">
            {oci?.period && (
              <span className="text-xs text-gray-500 font-mono">{oci.period}</span>
            )}
            <RefreshBtn onClick={fetchOci} isLoading={ociLoading} title={t('usage.refresh')} />
          </div>
        </div>

        {ociError ? (
          <div className="px-4 py-6 text-sm text-red-400">{ociError}</div>
        ) : oci ? (
          <div className="p-4 space-y-3">
            {/* total */}
            <div className="flex justify-between items-baseline pb-2 border-b border-gray-800">
              <span className="text-sm font-semibold text-gray-200">{t('usage.ociTotal')}</span>
              <span className="text-lg font-mono text-cyan-400">
                ${oci.total.toFixed(2)} <span className="text-xs text-gray-500">{oci.currency}</span>
              </span>
            </div>
            {/* service breakdown */}
            {oci.services.map((svc) => (
              <div key={svc.service} className="flex justify-between text-sm">
                <span className="text-gray-400">{svc.service}</span>
                <span className="font-mono text-gray-300">{formatCost(svc.cost)}</span>
              </div>
            ))}
            {oci.services.length === 0 && (
              <div className="text-xs text-gray-500">{t('usage.ociNoUsage')}</div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default UsagePanel;
