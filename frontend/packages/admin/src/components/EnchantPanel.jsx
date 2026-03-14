import React, { useEffect, useState, useCallback } from 'react';
import { Loader2, ChevronDown, ChevronRight, List, RefreshCw, Info } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getEnchantEntries, getEnchantEffects, getLinks } from '@mabi/shared/api/admin';
import { consumeSearchIntent } from '@mabi/shared/lib/searchIntent';
import SearchBar from '@mabi/shared/components/SearchBar';

const toRankLabel = (rank) => {
  const n = Number(rank);
  if (!Number.isFinite(n)) return String(rank ?? '');
  if (n >= 10 && n <= 15) return String.fromCharCode('A'.charCodeAt(0) + (n - 10));
  return String(n);
};

const toSlotLabel = (slot, t) => {
  if (slot === 0 || slot === '0' || slot === '접두' || slot === 'prefix') return t('enchants.prefix');
  if (slot === 1 || slot === '1' || slot === '접미' || slot === 'suffix') return t('enchants.suffix');
  return String(slot ?? 'Unknown');
};

const parseNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const getEffectToneClass = (effect) => {
  const text = String(effect?.raw_text || effect?.effect_text || effect?.effect_name || '');
  if (text.includes('감소')) return 'text-red-400';
  if (text.includes('증가')) return 'text-blue-300';
  const probe = parseNumber(effect?.min_value) ?? parseNumber(effect?.max_value) ?? parseNumber(effect?.effect_value);
  if (probe == null) return 'text-gray-300';
  return probe < 0 ? 'text-red-400' : 'text-blue-300';
};

const formatEffectText = (effect) => {
  if (effect?.raw_text) return effect.raw_text;
  const name = effect?.effect_name || effect?.effect_text || '';
  const min = effect?.min_value;
  const max = effect?.max_value;
  if (min != null && max != null) return `${name} ${min} ~ ${max}`;
  if (min != null) return `${name} ${min}`;
  return name || '-';
};

const EnchantPanel = () => {
  const { t } = useTranslation();
  const [entries, setEntries] = useState([]);
  const [effectsByEnchant, setEffectsByEnchant] = useState({});
  const [loadingEffects, setLoadingEffects] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [expandedEnchantIds, setExpandedEnchantIds] = useState({});
  const [_intent] = useState(() => consumeSearchIntent());
  const [searchQuery, setSearchQuery] = useState(_intent?.q || '');
  const [searchBy, setSearchBy] = useState(_intent?.by || 'name');
  const [pagination, setPagination] = useState({ limit: 100, offset: 0 });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = { limit: pagination.limit, offset: pagination.offset };
      if (searchQuery) {
        if (searchBy === 'id') params.id = searchQuery;
        else params.q = searchQuery;
      }
      const { data } = await getEnchantEntries(params);
      setEntries(data.rows || []);
    } catch (error) {
      console.error('Error fetching enchants:', error);
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

  const fetchEnchantEffects = async (enchantId) => {
    if (effectsByEnchant[enchantId] || loadingEffects[enchantId]) return;
    setLoadingEffects((prev) => ({ ...prev, [enchantId]: true }));
    try {
      let rows = [];
      try {
        const { data } = await getEnchantEffects(enchantId);
        rows = data;
      } catch {
        const { data: linksData } = await getLinks({ limit: 5000, offset: 0 });
        rows = (linksData.rows || [])
          .filter((link) => link.enchant_entry_id === enchantId)
          .sort((a, b) => (a.effect_order || 0) - (b.effect_order || 0));
      }
      setEffectsByEnchant((prev) => ({ ...prev, [enchantId]: rows }));
    } catch (error) {
      console.error(`Error fetching effects for enchant ${enchantId}:`, error);
      setEffectsByEnchant((prev) => ({ ...prev, [enchantId]: [] }));
    } finally {
      setLoadingEffects((prev) => ({ ...prev, [enchantId]: false }));
    }
  };

  const toggleEnchant = (id) => {
    setExpandedEnchantIds((prev) => ({ ...prev, [id]: !prev[id] }));
    fetchEnchantEffects(id);
  };

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
      <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <List className="w-5 h-5 text-cyan-500" />
          {t('enchants.title')}
        </h2>
        <div className="flex items-center gap-4">
          <SearchBar defaultQuery={_intent?.q} defaultBy={_intent?.by} onSearch={handleSearch} placeholder={t('enchants.searchPlaceholder')} />
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={pagination.offset === 0}
          >
            {t('enchants.prev')}
          </button>
          <span className="text-xs font-mono">
            {pagination.offset + 1} - {pagination.offset + entries.length}
          </span>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={entries.length < pagination.limit}
          >
            {t('enchants.next')}
          </button>
          <button onClick={fetchData} className="p-1 hover:text-cyan-400" title={t('enchants.refresh')}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="divide-y divide-gray-700">
        {isLoading && entries.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
          </div>
        ) : entries.length === 0 ? (
          <div className="px-6 py-8 text-center text-xs text-gray-500 uppercase tracking-wide">
            {t('enchants.noMatch')}
          </div>
        ) : entries.map((entry) => {
          const isExpanded = !!expandedEnchantIds[entry.id];
          const effects = effectsByEnchant[entry.id] || [];
          const isEffectsLoading = !!loadingEffects[entry.id];

          return (
            <div key={entry.id} className="transition-colors hover:bg-gray-700/30">
              <div
                className="px-6 py-4 flex items-center justify-between cursor-pointer"
                onClick={() => toggleEnchant(entry.id)}
              >
                <div className="flex items-center gap-4">
                  {isExpanded
                    ? <ChevronDown className="w-5 h-5 text-cyan-500" />
                    : <ChevronRight className="w-5 h-5 text-gray-500" />}
                  <div>
                    <span className={`text-xs font-bold uppercase mr-2 px-1.5 py-0.5 rounded ${
                      toSlotLabel(entry.slot, t) === t('enchants.prefix')
                        ? 'bg-blue-900/50 text-blue-300'
                        : 'bg-red-900/50 text-red-300'
                    }`}>
                      {toSlotLabel(entry.slot, t)}
                    </span>
                    <span className="text-lg font-black text-white">{entry.name}</span>
                    <span className="ml-3 text-sm text-gray-500">{t('enchants.rank', { rank: toRankLabel(entry.rank) })}</span>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-[10px] font-mono text-gray-500 bg-black/30 px-2 py-0.5 rounded">ID: {entry.id}</span>
                  <span className="text-xs font-bold text-cyan-600 uppercase tracking-tighter">
                    {t('enchants.effectCount', { count: entry.effect_count ?? '-' })}
                  </span>
                </div>
              </div>

              {isExpanded && (
                <div className="px-16 py-4 bg-black/20 space-y-3">
                  <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1">
                    {t('enchants.effectsAndConditions')}
                  </p>
                  {isEffectsLoading ? (
                    <div className="py-4 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-gray-600" />
                        <span className="text-xs text-gray-600 uppercase">{t('enchants.loadingEffects')}</span>
                      </div>
                    </div>
                  ) : effects.length > 0 ? (
                    <ul className="space-y-3">
                      {effects.map((eff, idx) => (
                        <li key={eff.id ?? idx} className="bg-gray-800/50 p-3 rounded-lg border border-gray-700/50 flex flex-col gap-1">
                          <div className="flex justify-between items-start gap-4">
                            <span className={`text-sm font-medium ${getEffectToneClass(eff)}`}>{formatEffectText(eff)}</span>
                          </div>
                          {eff.condition_text && (
                            <p className="text-[11px] text-gray-500 flex items-center gap-1 italic">
                              <Info className="w-3 h-3" />
                              {t('enchants.condition', { text: eff.condition_text })}
                            </p>
                          )}
                          <div className="flex gap-4 mt-1">
                            {eff.effect_order != null && (
                              <span className="text-[10px] text-gray-600">{t('enchants.order', { value: eff.effect_order })}</span>
                            )}
                            {(eff.min_value != null || eff.max_value != null) && (
                              <span className={`text-[10px] ${getEffectToneClass(eff)}`}>
                                {t('enchants.range', { min: eff.min_value ?? '-', max: eff.max_value ?? '-' })}
                              </span>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-gray-600 uppercase">{t('enchants.noEffects')}</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default EnchantPanel;
