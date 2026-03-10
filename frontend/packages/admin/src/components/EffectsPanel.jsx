import { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getEffects } from '@mabi/shared/api/admin';
import {
  panelOuter, panelHeader, panelTitle, panelEmpty,
  thRow, thCell, tdCell, tdCellMono, btnPagGray,
} from '@mabi/shared/styles';

const EffectsPanel = () => {
  const { t } = useTranslation();
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 100, offset: 0 });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await getEffects({ limit: pagination.limit, offset: pagination.offset });
      setRows(data.rows || []);
    } catch (error) {
      console.error('Error fetching effects:', error);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.offset, pagination.limit]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handlePrev = useCallback(() => {
    setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }));
  }, []);

  const handleNext = useCallback(() => {
    setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }));
  }, []);

  return (
    <div className={panelOuter}>
      <div className={panelHeader}>
        <h2 className={panelTitle}>{t('nav.items.effects')}</h2>
        <div className="flex items-center gap-4">
          <button onClick={handlePrev} className={btnPagGray} disabled={pagination.offset === 0}>
            Prev
          </button>
          <span className="text-xs font-mono">
            {pagination.offset + 1} - {pagination.offset + rows.length}
          </span>
          <button onClick={handleNext} className={btnPagGray} disabled={rows.length < pagination.limit}>
            Next
          </button>
          <button onClick={fetchData} className="p-1 hover:text-cyan-400" title="Refresh">
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {isLoading && rows.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
        </div>
      ) : rows.length === 0 ? (
        <div className={panelEmpty}>No effects found</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className={thRow}>
              <th className={thCell}>ID</th>
              <th className={thCell}>Name</th>
              <th className={thCell}>is_pct</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-700/30 transition-colors">
                <td className={tdCellMono}>{row.id}</td>
                <td className={tdCell}>{row.name}</td>
                <td className={tdCell}>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    row.is_pct
                      ? 'bg-emerald-900/50 text-emerald-300'
                      : 'bg-gray-700 text-gray-500'
                  }`}>
                    {row.is_pct ? 'true' : 'false'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default EffectsPanel;
