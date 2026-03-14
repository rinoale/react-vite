import { useCallback, useEffect, useState } from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getMuriasRelicOptions } from '@mabi/shared/api/admin';
import { consumeSearchIntent } from '@mabi/shared/lib/searchIntent';
import SearchBar from '@mabi/shared/components/SearchBar';
import {
  panelOuter, panelHeader, panelTitle, panelEmpty,
  thRow, thCell, tdCell, tdCellMono, tdCellSub, btnPagGray,
} from '@mabi/shared/styles';

const MuriasRelicOptionsPanel = () => {
  const { t } = useTranslation();
  const [_intent] = useState(() => consumeSearchIntent());
  const [rows, setRows] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });
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
      const { data } = await getMuriasRelicOptions(params);
      setRows(data.rows || []);
    } catch (error) {
      console.error('Error fetching murias relic options:', error);
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
        <h2 className={panelTitle}>{t('nav.items.murias_relic_options')}</h2>
        <div className="flex items-center gap-4">
          <SearchBar defaultQuery={_intent?.q} defaultBy={_intent?.by} onSearch={handleSearch} />
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
        <div className={panelEmpty}>No murias relic options found</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className={thRow}>
              <th className={thCell}>ID</th>
              <th className={thCell}>option_name</th>
              <th className={thCell}>type</th>
              <th className={thCell}>max_level</th>
              <th className={thCell}>min_level</th>
              <th className={thCell}>value_per_level</th>
              <th className={thCell}>option_unit</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700/50">
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-700/30 transition-colors">
                <td className={tdCellMono}>{row.id}</td>
                <td className={tdCell}>{row.option_name}</td>
                <td className={tdCellSub}>{row.type}</td>
                <td className={tdCellSub}>{row.max_level}</td>
                <td className={tdCellSub}>{row.min_level}</td>
                <td className={tdCellSub}>{row.value_per_level}</td>
                <td className={tdCellSub}>{row.option_unit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default MuriasRelicOptionsPanel;
