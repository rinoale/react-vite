import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { Loader2, ChevronDown, ChevronRight, Info, List, RefreshCw, Check, Image, Pencil, X, Save } from 'lucide-react';
import { getSummary, getEnchantEntries, getEnchantEffects, getLinks, getCorrections, approveCorrection, editCorrection } from '../api/admin';

const toRankLabel = (rank) => {
  const n = Number(rank);
  if (!Number.isFinite(n)) return String(rank ?? '');
  if (n >= 10 && n <= 15) {
    return String.fromCharCode('A'.charCodeAt(0) + (n - 10));
  }
  return String(n);
};

const toSlotLabel = (slot) => {
  if (slot === 0 || slot === '0' || slot === '접두' || slot === 'prefix') return 'Prefix';
  if (slot === 1 || slot === '1' || slot === '접미' || slot === 'suffix') return 'Suffix';
  return String(slot ?? 'Unknown');
};

const normalizeSummary = (summary) => ({
  enchants: summary?.enchants ?? summary?.enchant_entries ?? 0,
  effects: summary?.effects ?? summary?.enchant_effects ?? 0,
  enchantEffects: summary?.enchant_effects ?? summary?.enchant_links ?? 0,
  reforgeOptions: summary?.reforge_options ?? 0,
});

const formatEffectText = (effect) => {
  if (effect?.raw_text) return effect.raw_text;
  const name = effect?.effect_name || effect?.effect_text || '';
  const min = effect?.min_value;
  const max = effect?.max_value;
  if (min != null && max != null) return `${name} ${min} ~ ${max}`;
  if (min != null) return `${name} ${min}`;
  return name || '-';
};

const parseNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const getEffectToneClass = (effect) => {
  const text = String(effect?.raw_text || effect?.effect_text || effect?.effect_name || '');
  if (text.includes('감소')) return 'text-red-400';
  if (text.includes('증가')) return 'text-blue-300';

  const min = parseNumber(effect?.min_value);
  const max = parseNumber(effect?.max_value);
  const value = parseNumber(effect?.effect_value);
  const probe = min ?? max ?? value;

  if (probe == null) return 'text-gray-300';
  return probe < 0 ? 'text-red-400' : 'text-blue-300';
};

const API_BASE = import.meta.env.MABINOGI_TRADE_API_URL || 'http://localhost:8000';

const CorrectionsPanel = () => {
  const [corrections, setCorrections] = useState([]);
  const [status, setStatus] = useState('pending');
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });
  const [approvingIds, setApprovingIds] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);

  const fetchCorrections = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await getCorrections({ status, limit: pagination.limit, offset: pagination.offset });
      setCorrections(data);
    } catch (error) {
      console.error('Error fetching corrections:', error);
      setCorrections([]);
    } finally {
      setIsLoading(false);
    }
  }, [status, pagination.offset, pagination.limit]);

  useEffect(() => {
    fetchCorrections();
  }, [fetchCorrections]);

  const handleApprove = async (id) => {
    setApprovingIds((prev) => ({ ...prev, [id]: true }));
    try {
      await approveCorrection(id);
      setCorrections((prev) => prev.filter((c) => c.id !== id));
    } catch (error) {
      console.error('Error approving correction:', error);
    } finally {
      setApprovingIds((prev) => ({ ...prev, [id]: false }));
    }
  };

  const startEdit = (c) => {
    setEditingId(c.id);
    setEditText(c.corrected_text);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditText('');
  };

  const saveEdit = async (id) => {
    setSavingEdit(true);
    try {
      await editCorrection(id, editText);
      setCorrections((prev) =>
        prev.map((c) => (c.id === id ? { ...c, corrected_text: editText } : c)),
      );
      setEditingId(null);
    } catch (error) {
      console.error('Error editing correction:', error);
    } finally {
      setSavingEdit(false);
    }
  };

  const cropUrl = (c) => `${API_BASE}/admin/corrections/crop/${c.session_id}/${c.image_filename}`;

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
      <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Image className="w-5 h-5 text-cyan-500" />
          OCR CORRECTIONS
        </h2>
        <div className="flex items-center gap-4">
          <div className="flex rounded overflow-hidden border border-gray-600">
            {['pending', 'approved'].map((s) => (
              <button
                key={s}
                onClick={() => { setStatus(s); setPagination((p) => ({ ...p, offset: 0 })); }}
                className={`text-xs px-3 py-1 uppercase font-bold ${
                  status === s ? 'bg-cyan-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={pagination.offset === 0}
          >
            PREV
          </button>
          <span className="text-xs font-mono">
            {pagination.offset + 1} - {pagination.offset + corrections.length}
          </span>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={corrections.length < pagination.limit}
          >
            NEXT
          </button>
          <button onClick={fetchCorrections} className="p-1 hover:text-cyan-400" title="Refresh">
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="divide-y divide-gray-700">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
          </div>
        ) : corrections.length === 0 ? (
          <div className="px-6 py-8 text-center text-xs text-gray-500 uppercase tracking-wide">
            No {status} corrections found.
          </div>
        ) : (
          corrections.map((c) => (
            <div key={c.id} className="px-6 py-4 flex items-start gap-6 hover:bg-gray-700/30 transition-colors">
              <div className="flex-shrink-0 bg-black rounded border border-gray-600 overflow-hidden">
                <img
                  src={cropUrl(c)}
                  alt={`Line ${c.line_index}`}
                  className="h-8 min-w-[60px] max-w-[400px] object-contain"
                  style={{ imageRendering: 'pixelated' }}
                />
              </div>

              <div className="flex-1 min-w-0 space-y-1">
                {editingId === c.id ? (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-500 line-through">{c.original_text}</span>
                    <span className="text-gray-600">→</span>
                    <input
                      type="text"
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveEdit(c.id);
                        if (e.key === 'Escape') cancelEdit();
                      }}
                      autoFocus
                      className="flex-1 text-sm bg-gray-900 border border-cyan-600 rounded px-2 py-0.5 text-green-400 outline-none"
                    />
                  </div>
                ) : (
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm text-gray-500 line-through">{c.original_text}</span>
                    <span className="text-gray-600">→</span>
                    <span className="text-sm text-green-400 font-medium">{c.corrected_text}</span>
                  </div>
                )}
                <div className="flex items-center gap-3 flex-wrap">
                  {c.section && (
                    <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300">
                      {c.section}
                    </span>
                  )}
                  {c.ocr_model && (
                    <span className="text-[10px] font-mono text-gray-500 bg-black/30 px-1.5 py-0.5 rounded">
                      {c.ocr_model}
                    </span>
                  )}
                  {c.confidence != null && (
                    <span className="text-[10px] text-gray-500">
                      {(Number(c.confidence) * 100).toFixed(1)}%
                    </span>
                  )}
                  {c.fm_applied && (
                    <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-yellow-900/40 text-yellow-300">
                      FM
                    </span>
                  )}
                  {c.charset_mismatch && (
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-900/40 text-red-300" title={`Missing chars: ${c.charset_mismatch}`}>
                      CHARSET: {c.charset_mismatch}
                    </span>
                  )}
                  <span className="text-[10px] font-mono text-gray-600">ID: {c.id}</span>
                </div>
              </div>

              {status === 'pending' && (
                <div className="flex-shrink-0 flex items-center gap-2">
                  {editingId === c.id ? (
                    <>
                      <button
                        onClick={() => saveEdit(c.id)}
                        disabled={savingEdit}
                        className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-cyan-700 hover:bg-cyan-600 text-white disabled:opacity-50"
                      >
                        {savingEdit ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                        Save
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-gray-600 hover:bg-gray-500 text-white"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => startEdit(c)}
                        className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-gray-600 hover:bg-gray-500 text-white"
                      >
                        <Pencil className="w-3 h-3" />
                      </button>
                      <button
                        onClick={() => handleApprove(c.id)}
                        disabled={approvingIds[c.id]}
                        className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-green-700 hover:bg-green-600 text-white disabled:opacity-50"
                      >
                        {approvingIds[c.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                        Approve
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

const TABS = [
  { key: 'enchants', label: 'Enchants' },
  { key: 'corrections', label: 'Corrections' },
];

const Admin = () => {
  const [summary, setSummary] = useState(null);
  const [entries, setEntries] = useState([]);
  const [effectsByEnchant, setEffectsByEnchant] = useState({});
  const [loadingEffects, setLoadingEffects] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [expandedEnchantIds, setExpandedEnchantIds] = useState({});
  const [nameQuery, setNameQuery] = useState('');
  const [pagination, setPagination] = useState({ limit: 100, offset: 0 });
  const [activeTab, setActiveTab] = useState('enchants');

  useEffect(() => {
    fetchInitialData();
  }, [pagination.offset]);

  const stats = useMemo(() => normalizeSummary(summary), [summary]);
  const filteredEntries = useMemo(() => {
    const q = nameQuery.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((entry) => String(entry.name || '').toLowerCase().includes(q));
  }, [entries, nameQuery]);

  const fetchInitialData = async () => {
    setIsLoading(true);
    try {
      const [summaryRes, entriesRes] = await Promise.all([
        getSummary(),
        getEnchantEntries({ limit: pagination.limit, offset: pagination.offset }),
      ]);

      setSummary(summaryRes.data);
      setEntries(entriesRes.data.rows || []);
    } catch (error) {
      console.error('Error fetching admin data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchEnchantEffects = async (enchantId) => {
    if (effectsByEnchant[enchantId] || loadingEffects[enchantId]) return;

    setLoadingEffects((prev) => ({ ...prev, [enchantId]: true }));
    try {
      let rows = [];

      try {
        // New spec endpoint
        const { data } = await getEnchantEffects(enchantId);
        rows = data;
      } catch {
        // Backward-compat fallback for older backend shape
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
    setExpandedEnchantIds((prev) => {
      const isOpen = !!prev[id];
      return { ...prev, [id]: !isOpen };
    });
    fetchEnchantEffects(id);
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        <header className="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
          <div>
            <h1 className="text-4xl font-black text-white tracking-tight uppercase">
              ADMIN <span className="text-cyan-500">DASHBOARD</span>
            </h1>
            <p className="text-gray-400 text-sm mt-1">Database Validation & Maintenance</p>
          </div>
          {summary && (
            <div className="flex gap-4">
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">Enchants</span>
                <span className="text-lg font-bold text-cyan-400">{stats.enchants}</span>
              </div>
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">Effects</span>
                <span className="text-lg font-bold text-cyan-400">{stats.effects}</span>
              </div>
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">Enchant Effects</span>
                <span className="text-lg font-bold text-cyan-400">{stats.enchantEffects}</span>
              </div>
            </div>
          )}
        </header>

        <nav className="flex gap-1 mb-6">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-5 py-2 text-sm font-bold uppercase tracking-wide rounded-t-lg border border-b-0 ${
                activeTab === tab.key
                  ? 'bg-gray-800 text-cyan-400 border-gray-700'
                  : 'bg-gray-900 text-gray-500 border-gray-800 hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {activeTab === 'corrections' ? (
          <CorrectionsPanel />
        ) : isLoading && !summary ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mb-4" />
            <p className="text-gray-400 font-bold tracking-widest uppercase">Initializing Database...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-8">
            <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
              <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <List className="w-5 h-5 text-cyan-500" />
                  ENCHANT ENTRIES
                </h2>
                <div className="flex items-center gap-4">
                  <input
                    type="text"
                    value={nameQuery}
                    onChange={(e) => setNameQuery(e.target.value)}
                    placeholder="Search enchant name"
                    className="text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1 outline-none focus:border-cyan-500"
                  />
                  <button
                    onClick={() => {
                      setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }));
                    }}
                    className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
                    disabled={pagination.offset === 0}
                  >
                    PREV
                  </button>
                  <span className="text-xs font-mono">
                    {pagination.offset + 1} - {pagination.offset + entries.length} / {stats.enchants || '...'}
                  </span>
                  <button
                    onClick={() => {
                      setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }));
                    }}
                    className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
                    disabled={entries.length < pagination.limit}
                  >
                    NEXT
                  </button>
                  <button onClick={fetchInitialData} className="p-1 hover:text-cyan-400" title="Refresh">
                    <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>

              <div className="divide-y divide-gray-700">
                {filteredEntries.map((entry) => {
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
                          {isExpanded ? (
                            <ChevronDown className="w-5 h-5 text-cyan-500" />
                          ) : (
                            <ChevronRight className="w-5 h-5 text-gray-500" />
                          )}
                          <div>
                            <span
                              className={`text-xs font-bold uppercase mr-2 px-1.5 py-0.5 rounded ${
                                toSlotLabel(entry.slot) === 'Prefix'
                                  ? 'bg-blue-900/50 text-blue-300'
                                  : 'bg-red-900/50 text-red-300'
                              }`}
                            >
                              {toSlotLabel(entry.slot)}
                            </span>
                            <span className="text-lg font-black text-white">{entry.name}</span>
                            <span className="ml-3 text-sm text-gray-500">Rank {toRankLabel(entry.rank)}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-[10px] font-mono text-gray-500 bg-black/30 px-2 py-0.5 rounded">
                            ID: {entry.id}
                          </span>
                          <span className="text-xs font-bold text-cyan-600 uppercase tracking-tighter">
                            {entry.effect_count ?? '-'} EFFECTS
                          </span>
                        </div>
                      </div>

                      {isExpanded && (
                        <div className="px-16 py-4 bg-black/20 space-y-3">
                          <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1">
                            Enchant Effects & Conditions
                          </p>

                          {isEffectsLoading ? (
                            <div className="py-4 text-center">
                              <div className="flex items-center justify-center gap-2">
                                <Loader2 className="w-4 h-4 animate-spin text-gray-600" />
                                <span className="text-xs text-gray-600 uppercase">Loading effects...</span>
                              </div>
                            </div>
                          ) : effects.length > 0 ? (
                            <ul className="space-y-3">
                              {effects.map((eff, idx) => (
                                <li
                                  key={eff.id ?? idx}
                                  className="bg-gray-800/50 p-3 rounded-lg border border-gray-700/50 flex flex-col gap-1"
                                >
                                  <div className="flex justify-between items-start gap-4">
                                    <span className={`text-sm font-medium ${getEffectToneClass(eff)}`}>{formatEffectText(eff)}</span>
                                    {eff.effect_direction !== null && eff.effect_direction !== undefined && (
                                      <span
                                        className={`text-[10px] font-bold uppercase px-1.5 rounded ${
                                          Number(eff.effect_direction) === 0
                                            ? 'text-green-400 bg-green-900/20'
                                            : 'text-red-400 bg-red-900/20'
                                        }`}
                                      >
                                        {Number(eff.effect_direction) === 0 ? 'Increase' : 'Decrease'}
                                      </span>
                                    )}
                                  </div>

                                  {eff.condition_text && (
                                    <p className="text-[11px] text-gray-500 flex items-center gap-1 italic">
                                      <Info className="w-3 h-3" />
                                      Condition: {eff.condition_text}
                                    </p>
                                  )}

                                  <div className="flex gap-4 mt-1">
                                    {eff.effect_order != null && (
                                      <span className="text-[10px] text-gray-600">Order: {eff.effect_order}</span>
                                    )}
                                    {(eff.min_value != null || eff.max_value != null) && (
                                      <span className={`text-[10px] ${getEffectToneClass(eff)}`}>
                                        Range: {eff.min_value ?? '-'} ~ {eff.max_value ?? '-'}
                                      </span>
                                    )}
                                    {eff.effect_value != null && (
                                      <span className={`text-[10px] ${getEffectToneClass(eff)}`}>Value: {eff.effect_value}</span>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-xs text-gray-600 uppercase">No effects found for this enchant.</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                {filteredEntries.length === 0 && (
                  <div className="px-6 py-8 text-center text-xs text-gray-500 uppercase tracking-wide">
                    No enchant matched the search.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Admin;
