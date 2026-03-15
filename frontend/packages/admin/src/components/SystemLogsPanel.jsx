import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getSystemLogs, getSystemLogActions } from '@mabi/shared/api/admin';
import {
  panelOuter, panelHeader, panelTitle, panelEmpty,
  loadingCenter, loadingIcon, hoverRow, metaRow, flexCenter,
  thRow, thCell, tdCell, tdCellMono, tdCellSub,
  btnPagGray, badgeCyan, badgeOrange, badgeRed, badgeGreen,
  totalLabel, filterBar, logFilterSelect,
  paginationBar, paginationInfo,
} from '@mabi/shared/styles';

const SOURCE_BADGES = { admin: badgeOrange, system: badgeCyan };
const ACTION_BADGES = {
  'admin:create': badgeGreen,
  'admin:update': badgeOrange,
  'admin:delete': badgeRed,
  'system:create': badgeGreen,
  'system:update': badgeOrange,
  'system:delete': badgeRed,
};

const formatTime = (iso) => {
  if (!iso) return '-';
  return new Date(iso).toLocaleString('ko-KR', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
};

const DiffView = ({ before, after }) => {
  if (!before && !after) return <span className="text-gray-600">-</span>;

  const allKeys = [...new Set([...Object.keys(before || {}), ...Object.keys(after || {})])].sort();

  return (
    <pre className="text-[11px] leading-relaxed font-mono bg-gray-900/50 rounded p-2 overflow-x-auto max-w-xl">
      {allKeys.map((key) => {
        const bVal = before?.[key];
        const aVal = after?.[key];
        const bStr = bVal !== undefined ? JSON.stringify(bVal, null, 2) : undefined;
        const aStr = aVal !== undefined ? JSON.stringify(aVal, null, 2) : undefined;

        if (bStr === aStr) {
          return <span key={key} className="text-gray-500"> {key}: {bStr}\n</span>;
        }

        return (
          <span key={key}>
            {bStr !== undefined && <span className="text-red-400">-{key}: {bStr}\n</span>}
            {aStr !== undefined && <span className="text-green-400">+{key}: {aStr}\n</span>}
          </span>
        );
      })}
    </pre>
  );
};

const SystemLogsPanel = () => {
  const { t } = useTranslation();
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [actions, setActions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filterSource, setFilterSource] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });
  const [expandedIds, setExpandedIds] = useState({});

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [logsRes, actionsRes] = await Promise.all([
        getSystemLogs({
          source: filterSource,
          action: filterAction,
          limit: pagination.limit,
          offset: pagination.offset,
        }),
        getSystemLogActions(),
      ]);
      setLogs(logsRes.data.rows || []);
      setTotal(logsRes.data.total || 0);
      setActions(actionsRes.data || []);
    } catch (err) {
      console.error('Error fetching system logs:', err);
    } finally {
      setIsLoading(false);
    }
  }, [filterSource, filterAction, pagination.offset, pagination.limit]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const toggleExpand = useCallback((id) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
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
          <h2 className={panelTitle}>{t('systemLogs.title')}</h2>
          <span className={totalLabel}>{total.toLocaleString()} {t('systemLogs.total')}</span>
        </div>
        <button onClick={fetchData} className="p-1 hover:text-cyan-400" title={t('systemLogs.refresh')}>
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* filters */}
      <div className={filterBar}>
        <select
          value={filterSource}
          onChange={(e) => { setFilterSource(e.target.value); setPagination((p) => ({ ...p, offset: 0 })); }}
          className={logFilterSelect}
        >
          <option value="">{t('systemLogs.allSources')}</option>
          <option value="admin">admin</option>
          <option value="system">system</option>
        </select>
        <select
          value={filterAction}
          onChange={(e) => { setFilterAction(e.target.value); setPagination((p) => ({ ...p, offset: 0 })); }}
          className={logFilterSelect}
        >
          <option value="">{t('systemLogs.allActions')}</option>
          {actions.map((a) => (
            <option key={a.action} value={a.action}>
              {a.action} ({a.count})
            </option>
          ))}
        </select>
      </div>

      {/* table */}
      <table className="w-full text-sm">
        <thead>
          <tr className={thRow}>
            <th className={thCell} />
            <th className={thCell}>{t('systemLogs.colSource')}</th>
            <th className={thCell}>{t('systemLogs.colAction')}</th>
            <th className={thCell}>{t('systemLogs.colTarget')}</th>
            <th className={thCell}>{t('systemLogs.colUser')}</th>
            <th className={thCell}>{t('systemLogs.colTime')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700/50">
          {logs.map((log) => {
            const isExpanded = !!expandedIds[log.id];
            const hasDiff = log.before || log.after;
            return (
              <React.Fragment key={log.id}>
                <tr className={`${hoverRow} ${hasDiff ? 'cursor-pointer' : ''}`} onClick={hasDiff ? () => toggleExpand(log.id) : undefined}>
                  <td className={tdCell}>
                    {hasDiff && (isExpanded
                      ? <ChevronDown className="w-4 h-4 text-cyan-500" />
                      : <ChevronRight className="w-4 h-4 text-gray-500" />
                    )}
                  </td>
                  <td className={tdCell}>
                    <span className={SOURCE_BADGES[log.source] || badgeCyan}>{log.source}</span>
                  </td>
                  <td className={tdCell}>
                    <span className={ACTION_BADGES[log.action] || badgeCyan}>{log.action}</span>
                  </td>
                  <td className={tdCellSub}>
                    {log.target_type ? `${log.target_type}` : '-'}
                    {log.target_id && <span className={tdCellMono}> #{String(log.target_id).slice(0, 8)}</span>}
                  </td>
                  <td className={tdCellSub}>{log.user_id ? String(log.user_id).slice(0, 8) : '-'}</td>
                  <td className={tdCellSub}>{formatTime(log.created_at)}</td>
                </tr>
                {isExpanded && (
                  <tr>
                    <td colSpan={6} className="px-6 py-3 bg-black/20">
                      <DiffView before={log.before} after={log.after} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
          {logs.length === 0 && (
            <tr>
              <td colSpan={6} className={panelEmpty}>{t('systemLogs.noLogs')}</td>
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
              {t('systemLogs.prev')}
            </button>
            <button
              onClick={() => setPagination((p) => ({ ...p, offset: p.offset + p.limit }))}
              className={btnPagGray}
              disabled={pageEnd >= total}
            >
              {t('systemLogs.next')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default SystemLogsPanel;
