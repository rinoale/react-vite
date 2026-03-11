import { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getActivityLogs, getActivityActions } from '@mabi/shared/api/admin';
import {
  panelOuter, panelHeader, panelTitle, panelEmpty,
  loadingCenter, loadingIcon, hoverRow, metaRow, flexCenter,
  thRow, thCell, tdCell, tdCellMono, tdCellSub, tdCellTrunc,
  btnPagGray, badgeCyan, badgeGreen, badgeOrange, badgeRed, badgeBlue, badgePurple,
  metaLabel, totalLabel, filterBar, filterSelect, filterInput,
  paginationBar, paginationInfo, iconSm,
} from '@mabi/shared/styles';

const ACTION_BADGES = {
  search: badgeBlue,
  listing_viewed: badgeCyan,
  listing_created: badgeGreen,
  listing_listed: badgeGreen,
  listing_sold: badgeOrange,
  listing_drafted: badgePurple,
  listing_deleted: badgeRed,
};

const formatTime = (iso) => {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('ko-KR', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
};

const MetadataCell = ({ metadata }) => {
  if (!metadata || Object.keys(metadata).length === 0) return <span className="text-gray-600">-</span>;
  return (
    <span className={metaLabel}>
      {Object.entries(metadata).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')}
    </span>
  );
};

const ActivityLogsPanel = () => {
  const { t } = useTranslation();
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [actions, setActions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filterAction, setFilterAction] = useState('');
  const [filterUserId, setFilterUserId] = useState('');
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [logsRes, actionsRes] = await Promise.all([
        getActivityLogs({
          action: filterAction,
          userId: filterUserId || undefined,
          limit: pagination.limit,
          offset: pagination.offset,
        }),
        getActivityActions(),
      ]);
      setLogs(logsRes.data.rows || []);
      setTotal(logsRes.data.total || 0);
      setActions(actionsRes.data || []);
    } catch (err) {
      console.error('Error fetching activity logs:', err);
    } finally {
      setIsLoading(false);
    }
  }, [filterAction, filterUserId, pagination.offset, pagination.limit]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleFilterChange = useCallback((action) => {
    setFilterAction(action);
    setPagination((p) => ({ ...p, offset: 0 }));
  }, []);

  const handleUserIdSubmit = useCallback((e) => {
    e.preventDefault();
    setPagination((p) => ({ ...p, offset: 0 }));
  }, []);

  if (isLoading && logs.length === 0) {
    return (
      <div className={loadingCenter}>
        <Loader2 className={loadingIcon} />
      </div>
    );
  }

  const pageStart = pagination.offset + 1;
  const pageEnd = Math.min(pagination.offset + pagination.limit, total);

  return (
    <div className={panelOuter}>
      {/* panel-header */}
      <div className={panelHeader}>
        <div className={flexCenter}>
          <h2 className={panelTitle}>{t('activity.title')}</h2>
          <span className={totalLabel}>{total.toLocaleString()} {t('activity.total')}</span>
        </div>
        <button onClick={fetchData} className="p-1 hover:text-cyan-400" title={t('activity.refresh')}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* filters */}
      <div className={filterBar}>
        {/* action-filter */}
        <select
          value={filterAction}
          onChange={(e) => handleFilterChange(e.target.value)}
          className={filterSelect}
        >
          <option value="">{t('activity.allActions')}</option>
          {actions.map((a) => (
            <option key={a.action} value={a.action}>
              {a.action} ({a.count})
            </option>
          ))}
        </select>

        {/* user-id-filter */}
        <form onSubmit={handleUserIdSubmit} className={flexCenter}>
          <Search className={iconSm} />
          <input
            type="text"
            value={filterUserId}
            onChange={(e) => setFilterUserId(e.target.value.replace(/\D/g, ''))}
            placeholder={t('activity.userIdPlaceholder')}
            className={filterInput}
          />
        </form>
      </div>

      {/* table */}
      <table className="w-full text-sm">
        <thead>
          <tr className={thRow}>
            <th className={thCell}>ID</th>
            <th className={thCell}>{t('activity.colAction')}</th>
            <th className={thCell}>{t('activity.colUser')}</th>
            <th className={thCell}>{t('activity.colTarget')}</th>
            <th className={thCell}>{t('activity.colMetadata')}</th>
            <th className={thCell}>{t('activity.colTime')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {logs.map((log) => (
            <tr key={log.id} className={hoverRow}>
              <td className={tdCellMono}>{log.id}</td>
              <td className={tdCell}>
                <span className={ACTION_BADGES[log.action] || badgeCyan}>{log.action}</span>
              </td>
              <td className={tdCellSub}>{log.user_id ?? '-'}</td>
              <td className={tdCellSub}>
                {log.target_type ? `${log.target_type}${log.target_id != null ? `#${log.target_id}` : ''}` : '-'}
              </td>
              <td className={tdCellTrunc}>
                <MetadataCell metadata={log.metadata} />
              </td>
              <td className={tdCellSub}>{formatTime(log.created_at)}</td>
            </tr>
          ))}
          {logs.length === 0 && (
            <tr>
              <td colSpan={6} className={panelEmpty}>{t('activity.noLogs')}</td>
            </tr>
          )}
        </tbody>
      </table>

      {/* pagination */}
      {total > 0 && (
        <div className={paginationBar}>
          <span className={paginationInfo}>{pageStart}-{pageEnd} / {total.toLocaleString()}</span>
          <div className={metaRow}>
            <button
              onClick={() => setPagination((p) => ({ ...p, offset: Math.max(0, p.offset - p.limit) }))}
              className={btnPagGray}
              disabled={pagination.offset === 0}
            >
              {t('activity.prev')}
            </button>
            <button
              onClick={() => setPagination((p) => ({ ...p, offset: p.offset + p.limit }))}
              className={btnPagGray}
              disabled={pageEnd >= total}
            >
              {t('activity.next')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ActivityLogsPanel;
