import { useCallback, useEffect, useState } from 'react';
import { Check, Loader2, RefreshCw, X as XIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getGameItems } from '@mabi/shared/api/admin';
import { consumeSearchIntent } from '@mabi/shared/lib/searchIntent';
import SearchBar from '@mabi/shared/components/SearchBar';
import {
  panelOuter, panelHeader, panelTitle, panelEmpty,
  thRow, thCell, tdCell, tdCellSub, btnPagGray,
} from '@mabi/shared/styles';

const GameItemsPanel = () => {
  const { t } = useTranslation();
  const [_intent] = useState(() => consumeSearchIntent());
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 100, offset: 0 });
  const [searchQuery, setSearchQuery] = useState(_intent?.q || '');
  const [searchBy, setSearchBy] = useState(_intent?.by || 'name');

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = { limit: pagination.limit, offset: pagination.offset };
      if (searchQuery) {
        if (searchBy === 'id') params.id = searchQuery;
        else params.q = searchQuery;
      }
      const { data } = await getGameItems(params);
      setRows(data.rows || []);
    } catch (error) {
      console.error('Error fetching game items:', error);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.offset, pagination.limit, searchQuery, searchBy]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSearch = useCallback(({ query, by }) => {
    setSearchQuery(query);
    setSearchBy(by);
    setPagination((prev) => ({ ...prev, offset: 0 }));
  }, []);

  const handlePrev = useCallback(() => {
    setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }));
  }, []);

  const handleNext = useCallback(() => {
    setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }));
  }, []);

  return (
    <div className={panelOuter}>
      <div className={panelHeader}>
        <h2 className={panelTitle}>{t('gameItems.title')}</h2>
        <div className="flex items-center gap-4">
          <SearchBar defaultQuery={_intent?.q} defaultBy={_intent?.by} onSearch={handleSearch} placeholder={t('gameItems.searchPlaceholder')} />
          <button onClick={handlePrev} className={btnPagGray} disabled={pagination.offset === 0}>
            {t('gameItems.prev')}
          </button>
          <span className="text-xs font-mono">
            {pagination.offset + 1} - {pagination.offset + rows.length}
          </span>
          <button onClick={handleNext} className={btnPagGray} disabled={rows.length < pagination.limit}>
            {t('gameItems.next')}
          </button>
          <button onClick={fetchData} className="p-1 hover:text-cyan-400" title={t('gameItems.refresh')}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {isLoading && rows.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
        </div>
      ) : rows.length === 0 ? (
        <div className={panelEmpty}>{t('gameItems.noItems')}</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className={thRow}>
              <th className={thCell}>{t('gameItems.colName')}</th>
              <th className={thCell}>{t('gameItems.colType')}</th>
              <th className={`${thCell} text-center`}>{t('gameItems.colSearchable')}</th>
              <th className={`${thCell} text-center`}>{t('gameItems.colTradable')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-700/30 transition-colors">
                <td className={tdCell}>{row.name}</td>
                <td className={tdCellSub}>{row.type || '-'}</td>
                <td className={`${tdCell} text-center`}>
                  {row.searchable ? <Check className="w-3.5 h-3.5 text-emerald-400 inline" /> : <XIcon className="w-3.5 h-3.5 text-gray-600 inline" />}
                </td>
                <td className={`${tdCell} text-center`}>
                  {row.tradable ? <Check className="w-3.5 h-3.5 text-emerald-400 inline" /> : <XIcon className="w-3.5 h-3.5 text-gray-600 inline" />}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default GameItemsPanel;
