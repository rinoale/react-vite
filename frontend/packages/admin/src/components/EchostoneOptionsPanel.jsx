import { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getEchostoneOptions } from '@mabi/shared/api/admin';
import {
  panelOuter, panelHeader, panelTitle, panelEmpty,
  thRow, thCell, tdCell, tdCellMono, tdCellSub, btnPagGray,
} from '@mabi/shared/styles';

const TYPE_COLORS = {
  red: 'bg-red-900/50 text-red-300',
  blue: 'bg-blue-900/50 text-blue-300',
  yellow: 'bg-yellow-900/50 text-yellow-300',
  silver: 'bg-gray-600/50 text-gray-300',
  black: 'bg-gray-900 text-gray-300 border border-gray-600',
};

const EchostoneOptionsPanel = () => {
  const { t } = useTranslation();
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 100, offset: 0 });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await getEchostoneOptions({ limit: pagination.limit, offset: pagination.offset });
      setRows(data.rows || []);
    } catch (error) {
      console.error('Error fetching echostone options:', error);
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
        <h2 className={panelTitle}>{t('nav.items.echostone_options')}</h2>
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
        <div className={panelEmpty}>No echostone options found</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className={thRow}>
              <th className={thCell}>ID</th>
              <th className={thCell}>option_name</th>
              <th className={thCell}>type</th>
              <th className={thCell}>max_level</th>
              <th className={thCell}>min_level</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-700/30 transition-colors">
                <td className={tdCellMono}>{row.id}</td>
                <td className={tdCell}>{row.option_name}</td>
                <td className={tdCell}>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${TYPE_COLORS[row.type] || 'bg-gray-700 text-gray-400'}`}>
                    {row.type}
                  </span>
                </td>
                <td className={tdCellSub}>{row.max_level}</td>
                <td className={tdCellSub}>{row.min_level}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default EchostoneOptionsPanel;
