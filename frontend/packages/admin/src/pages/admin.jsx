import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Loader2, ChevronDown, ChevronRight, Info, List, RefreshCw, Check, Image, Pencil, X, Save, Package, Trash2, Tag, Plus, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getSummary, getEnchantEntries, getEnchantEffects, getLinks, getCorrections, approveCorrection, editCorrection, truncateCorrections, getListings, getListingDetail, getTags, createTag, deleteTag, searchTagEntities, bulkCreateTags, getUniqueTags, deleteTagById, getTagDetail, updateTagWeight, updateTagTargetWeight } from '@mabi/shared/api/admin';
import { getTagColor } from '@mabi/shared/lib/tagColors';
import CustomSelect from '@mabi/shared/components/CustomSelect';

const toRankLabel = (rank) => {
  const n = Number(rank);
  if (!Number.isFinite(n)) return String(rank ?? '');
  if (n >= 10 && n <= 15) {
    return String.fromCharCode('A'.charCodeAt(0) + (n - 10));
  }
  return String(n);
};

const toSlotLabel = (slot, t) => {
  if (slot === 0 || slot === '0' || slot === '접두' || slot === 'prefix') return t('enchants.prefix');
  if (slot === 1 || slot === '1' || slot === '접미' || slot === 'suffix') return t('enchants.suffix');
  return String(slot ?? 'Unknown');
};

const normalizeSummary = (summary) => ({
  enchants: summary?.enchants ?? summary?.enchant_entries ?? 0,
  effects: summary?.effects ?? summary?.enchant_effects ?? 0,
  enchantEffects: summary?.enchant_effects ?? summary?.enchant_links ?? 0,
  reforgeOptions: summary?.reforge_options ?? 0,
  listings: summary?.listings ?? 0,
  gameItems: summary?.game_items ?? 0,
  tags: summary?.tags ?? 0,
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

const ATTR_LABELS = {
  damage: '공격력', magic_damage: '마법공격력', additional_damage: '추가대미지',
  balance: '밸런스', defense: '방어', protection: '보호',
  magic_defense: '마법방어', magic_protection: '마법보호',
  durability: '내구력', piercing_level: '관통 레벨',
};

const API_BASE = import.meta.env.MABINOGI_TRADE_API_URL || 'http://localhost:8000';

const CorrectionsPanel = () => {
  const { t } = useTranslation();
  const [corrections, setCorrections] = useState([]);
  const [status, setStatus] = useState('pending');
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });
  const [approvingIds, setApprovingIds] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [truncating, setTruncating] = useState(false);

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

  const handleTruncate = async () => {
    if (!window.confirm(t('corrections.truncateConfirm'))) return;
    setTruncating(true);
    try {
      await truncateCorrections();
      setCorrections([]);
      setPagination((p) => ({ ...p, offset: 0 }));
    } catch (error) {
      console.error('Error truncating corrections:', error);
    } finally {
      setTruncating(false);
    }
  };

  const cropUrl = (c) => `${API_BASE}/admin/corrections/crop/${c.session_id}/${c.image_filename}`;

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
      <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Image className="w-5 h-5 text-cyan-500" />
          {t('corrections.title')}
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
                {t(`corrections.${s}`)}
              </button>
            ))}
          </div>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={pagination.offset === 0}
          >
            {t('corrections.prev')}
          </button>
          <span className="text-xs font-mono">
            {pagination.offset + 1} - {pagination.offset + corrections.length}
          </span>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={corrections.length < pagination.limit}
          >
            {t('corrections.next')}
          </button>
          <button onClick={fetchCorrections} className="p-1 hover:text-cyan-400" title={t('corrections.refresh')}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={handleTruncate}
            disabled={truncating}
            className="p-1 hover:text-red-400 text-gray-500 disabled:opacity-50"
            title={t('corrections.truncate')}
          >
            <Trash2 className={`w-4 h-4 ${truncating ? 'animate-pulse' : ''}`} />
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
            {t('corrections.noCorrections', { status })}
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
                    <span className="text-gray-600">&rarr;</span>
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
                    <span className="text-gray-600">&rarr;</span>
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
                  {/* continuation stitch: warn admin that crop is merged from multiple lines */}
                  {c.is_stitched && (
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-orange-900/40 text-orange-300" title="Crop is stitched from multiple lines">
                      ⚠ STITCHED
                    </span>
                  )}
                  <span className="text-[10px] font-mono text-gray-600">ID: {c.id}</span>
                  {c.created_at && (
                    <span className="text-[10px] text-gray-600">{new Date(c.created_at).toLocaleString()}</span>
                  )}
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
                        {t('corrections.save')}
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
                        {t('corrections.approve')}
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

const ENTITY_TYPES = [
  { value: 'reforge_option', label: 'Reforge Option' },
  { value: 'game_item', label: 'Game Item' },
  { value: 'listing', label: 'Listing' },
  { value: 'enchant', label: 'Enchant' },
];

const TagBadge = ({ name, weight }) => {
  const c = getTagColor(weight);
  return (
    <span className={`text-sm font-bold px-2 py-0.5 rounded ${c.bg} ${c.text} group-hover:ring-1 ring-emerald-500/50`}>
      {name}
    </span>
  );
};

const TagTargetRow = ({ tgt, editingWeight, onStartEdit, onSaveWeight, onCancelEdit, onChangeWeight, onDelete, t }) => (
  <div className="flex items-center gap-3 py-1 px-2 rounded hover:bg-gray-800/50">
    <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-gray-700 text-gray-400 min-w-[80px] text-center">
      {tgt.target_type}
    </span>
    <span className="text-xs text-gray-300 flex-1">
      {tgt.target_display_name || `#${tgt.target_id}`}
    </span>
    <span className="text-[10px] text-gray-500 mr-1">{t('tags.targetWeight')}</span>
    {editingWeight != null ? (
      <span className="flex items-center gap-1">
        <input
          type="number"
          value={editingWeight}
          onChange={onChangeWeight}
          onKeyDown={(e) => { if (e.key === 'Enter') onSaveWeight(); if (e.key === 'Escape') onCancelEdit(); }}
          className="text-xs bg-gray-800 border border-emerald-600 rounded px-1.5 py-0.5 w-14 outline-none"
          autoFocus
        />
        <button onClick={onSaveWeight} className="p-0.5 text-emerald-400 hover:text-emerald-300"><Check className="w-3 h-3" /></button>
        <button onClick={onCancelEdit} className="p-0.5 text-gray-500 hover:text-gray-300"><X className="w-3 h-3" /></button>
      </span>
    ) : (
      <button onClick={onStartEdit} className="text-xs font-mono text-orange-400 hover:text-orange-300 px-1.5 py-0.5 rounded bg-gray-800 hover:bg-gray-700">
        {tgt.weight}
      </button>
    )}
    <button onClick={onDelete} className="p-0.5 text-gray-500 hover:text-red-400">
      <X className="w-3 h-3" />
    </button>
  </div>
);

const TagsPanel = () => {
  const { t } = useTranslation();

  // --- Section A: Bulk Tag Creator ---
  const [searchType, setSearchType] = useState('game_item');
  const [searchQuery, setSearchQuery] = useState('');
  const [likeSearch, setLikeSearch] = useState(true);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedTargets, setSelectedTargets] = useState([]);
  const [tagName, setTagName] = useState('');
  const [tagWeight, setTagWeight] = useState(0);
  const [creating, setCreating] = useState(false);
  const [createResult, setCreateResult] = useState(null);
  const suggestionsRef = useRef(null);
  const debounceRef = useRef(null);

  // --- Section B: Unique Tags List ---
  const [tags, setTags] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });

  // Detail state
  const [expandedTagId, setExpandedTagId] = useState(null);
  const [tagDetail, setTagDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [editingTagWeight, setEditingTagWeight] = useState(null);
  const [editingTargetWeights, setEditingTargetWeights] = useState({});
  const [targetTypeFilter, setTargetTypeFilter] = useState(null);

  // --- Fetch unique tags ---
  const fetchTags = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await getUniqueTags({ limit: pagination.limit, offset: pagination.offset });
      setTags(data.rows || []);
    } catch (error) {
      console.error('Error fetching tags:', error);
      setTags([]);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.offset, pagination.limit]);

  useEffect(() => { fetchTags(); }, [fetchTags]);

  // Close suggestions on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  // --- Search logic ---
  const handleSearchChange = useCallback((e) => {
    const q = e.target.value;
    setSearchQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await searchTagEntities(searchType, q.trim(), { like: likeSearch });
        setSuggestions(data);
        setShowSuggestions(true);
      } catch (error) {
        console.error('Error searching entities:', error);
      }
    }, 300);
  }, [searchType, likeSearch]);

  const handleSearchFocus = useCallback(() => {
    if (suggestions.length > 0) setShowSuggestions(true);
  }, [suggestions.length]);

  const handleAddTarget = useCallback((entity) => {
    setSelectedTargets((prev) => {
      const key = `${searchType}:${entity.id}`;
      if (prev.some((st) => `${st.target_type}:${st.target_id}` === key)) return prev;
      return [...prev, { target_type: searchType, target_id: entity.id, name: entity.name }];
    });
  }, [searchType]);

  const handleSelectAll = useCallback(() => {
    setSelectedTargets((prev) => {
      const newTargets = suggestions.filter((ent) => {
        const key = `${searchType}:${ent.id}`;
        return !prev.some((st) => `${st.target_type}:${st.target_id}` === key);
      }).map((ent) => ({ target_type: searchType, target_id: ent.id, name: ent.name }));
      return newTargets.length > 0 ? [...prev, ...newTargets] : prev;
    });
  }, [suggestions, searchType]);

  const handleRemoveTarget = useCallback((index) => {
    setSelectedTargets((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleSearchTypeChange = useCallback((e) => setSearchType(e.target.value), []);
  const handleLikeChange = useCallback((e) => setLikeSearch(e.target.checked), []);
  const handleTagNameChange = useCallback((e) => setTagName(e.target.value), []);
  const handleTagWeightChange = useCallback((e) => setTagWeight(Number(e.target.value) || 0), []);

  // Reset search when type changes
  useEffect(() => {
    setSearchQuery('');
    setSuggestions([]);
  }, [searchType]);

  // --- Create bulk tag ---
  const handleCreate = useCallback(async () => {
    const name = tagName.trim();
    if (!name) return;
    setCreating(true);
    setCreateResult(null);
    try {
      const { data } = await bulkCreateTags({
        targets: selectedTargets.map(({ target_type, target_id }) => ({ target_type, target_id })),
        names: [name],
        weight: tagWeight,
      });
      setCreateResult(data);
      if (data.created > 0) {
        setSelectedTargets([]);
        setTagName('');
        setTagWeight(0);
        fetchTags();
      }
    } catch (error) {
      console.error('Error creating bulk tags:', error);
    } finally {
      setCreating(false);
    }
  }, [tagName, tagWeight, selectedTargets, fetchTags]);

  const handleFormKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleCreate();
  }, [handleCreate]);

  // --- Pagination ---
  const handlePrevPage = useCallback(() => {
    setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }));
  }, []);

  const handleNextPage = useCallback(() => {
    setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }));
  }, []);

  // --- Tag detail ---
  const fetchTagDetail = useCallback(async (tagId) => {
    setLoadingDetail(true);
    try {
      const { data } = await getTagDetail(tagId);
      setTagDetail(data);
      setEditingTagWeight(null);
      setEditingTargetWeights({});
      setTargetTypeFilter(null);
    } catch (error) {
      console.error('Error fetching tag detail:', error);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const toggleDetail = useCallback((tagId) => {
    if (expandedTagId === tagId) {
      setExpandedTagId(null);
      setTagDetail(null);
    } else {
      setExpandedTagId(tagId);
      fetchTagDetail(tagId);
    }
  }, [expandedTagId, fetchTagDetail]);

  const handleDeleteTag = useCallback(async (tagId) => {
    if (!window.confirm(t('tags.deleteTagConfirm'))) return;
    try {
      await deleteTagById(tagId);
      setTags((prev) => prev.filter((tg) => tg.id !== tagId));
      if (expandedTagId === tagId) {
        setExpandedTagId(null);
        setTagDetail(null);
      }
    } catch (error) {
      console.error('Error deleting tag:', error);
    }
  }, [expandedTagId, t]);

  const handleDeleteTarget = useCallback(async (tagTargetId) => {
    if (!window.confirm(t('tags.deleteConfirm'))) return;
    try {
      await deleteTag(tagTargetId);
      if (tagDetail) {
        fetchTagDetail(tagDetail.id);
        fetchTags();
      }
    } catch (error) {
      console.error('Error deleting target:', error);
    }
  }, [tagDetail, fetchTagDetail, fetchTags, t]);

  const handleSaveTagWeight = useCallback(async () => {
    if (editingTagWeight == null || !tagDetail) return;
    try {
      await updateTagWeight(tagDetail.id, editingTagWeight);
      setTagDetail((prev) => ({ ...prev, weight: editingTagWeight }));
      setEditingTagWeight(null);
      fetchTags();
    } catch (error) {
      console.error('Error updating tag weight:', error);
    }
  }, [editingTagWeight, tagDetail, fetchTags]);

  const handleCancelTagWeightEdit = useCallback(() => setEditingTagWeight(null), []);
  const handleStartTagWeightEdit = useCallback(() => setEditingTagWeight(tagDetail?.weight ?? 0), [tagDetail]);
  const handleTagWeightEditChange = useCallback((e) => setEditingTagWeight(Number(e.target.value) || 0), []);

  const handleTagWeightEditKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleSaveTagWeight();
    if (e.key === 'Escape') handleCancelTagWeightEdit();
  }, [handleSaveTagWeight, handleCancelTagWeightEdit]);

  const handleSaveTargetWeight = useCallback(async (ttId) => {
    const w = editingTargetWeights[ttId];
    if (w == null) return;
    try {
      await updateTagTargetWeight(ttId, w);
      setTagDetail((prev) => ({
        ...prev,
        targets: prev.targets.map((tgt) => tgt.id === ttId ? { ...tgt, weight: w } : tgt),
      }));
      setEditingTargetWeights((prev) => { const n = { ...prev }; delete n[ttId]; return n; });
    } catch (error) {
      console.error('Error updating target weight:', error);
    }
  }, [editingTargetWeights]);

  const startTargetWeightEdit = useCallback((tgt) => {
    setEditingTargetWeights((prev) => ({ ...prev, [tgt.id]: tgt.weight }));
  }, []);

  const cancelTargetWeightEdit = useCallback((ttId) => {
    setEditingTargetWeights((prev) => { const n = { ...prev }; delete n[ttId]; return n; });
  }, []);

  const changeTargetWeight = useCallback((ttId, e) => {
    setEditingTargetWeights((prev) => ({ ...prev, [ttId]: Number(e.target.value) || 0 }));
  }, []);

  const canCreate = !creating && tagName.trim().length > 0;

  return (
    <div className="space-y-6">
      {/* Section A: Bulk Tag Creator */}
      <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
        <div className="bg-gray-700/50 px-6 py-4">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Tag className="w-5 h-5 text-emerald-500" />
            {t('tags.title')}
          </h2>
        </div>

        {/* Search row */}
        <div className="px-6 py-4 bg-gray-900/50 border-b border-gray-700 flex items-center gap-3 flex-wrap">
          <CustomSelect
            value={searchType}
            onChange={handleSearchTypeChange}
            options={ENTITY_TYPES}
            triggerClassName="text-xs bg-gray-800 border border-gray-600 rounded px-2 py-1.5 focus:border-emerald-500"
          />

          <label className="flex items-center gap-1 text-xs text-gray-400 cursor-pointer select-none">
            <input type="checkbox" checked={likeSearch} onChange={handleLikeChange} className="accent-emerald-500" />
            {t('bulkTag.likeSearch')}
          </label>

          <div className="relative flex-1 min-w-[200px] max-w-xs" ref={suggestionsRef}>
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-500 w-3 h-3" />
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              onFocus={handleSearchFocus}
              placeholder={t('bulkTag.searchPlaceholder')}
              className="text-xs bg-gray-800 border border-gray-600 rounded pl-7 pr-2 py-1.5 w-full outline-none focus:border-emerald-500"
            />
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute z-50 mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-48 overflow-auto">
                {suggestions.map((ent) => {
                  const alreadyAdded = selectedTargets.some((st) => st.target_type === searchType && st.target_id === ent.id);
                  return (
                    <button
                      key={ent.id}
                      onClick={() => handleAddTarget(ent)}
                      disabled={alreadyAdded}
                      className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between transition-colors ${alreadyAdded ? 'opacity-40 cursor-not-allowed' : 'hover:bg-gray-700'}`}
                    >
                      <span><span className="text-gray-400 mr-1">#{ent.id}</span> {ent.name}</span>
                      {!alreadyAdded && <Plus className="w-3 h-3 text-emerald-400" />}
                    </button>
                  );
                })}
                <button onClick={handleSelectAll} className="w-full text-center px-3 py-1.5 text-xs font-bold text-emerald-400 hover:bg-gray-700 border-t border-gray-700 transition-colors">
                  {t('tags.selectAll')}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Basket */}
        {selectedTargets.length > 0 && (
          <div className="px-6 py-3 border-b border-gray-700 flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-bold uppercase text-gray-500 mr-1">
              {t('bulkTag.selected', { count: selectedTargets.length })}
            </span>
            {selectedTargets.map((tgt, i) => (
              <span key={`${tgt.target_type}:${tgt.target_id}`} className="inline-flex items-center gap-1 text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                <span className="text-[9px] font-bold uppercase text-gray-500">{tgt.target_type.replace('_', ' ')}</span>
                {tgt.name}
                <button onClick={() => handleRemoveTarget(i)} className="text-gray-500 hover:text-red-400 ml-0.5">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Form row */}
        <div className="px-6 py-4 flex items-center gap-3 flex-wrap">
          <input
            type="text"
            value={tagName}
            onChange={handleTagNameChange}
            placeholder={t('bulkTag.tagName')}
            maxLength={5}
            onKeyDown={handleFormKeyDown}
            className="text-xs bg-gray-800 border border-gray-600 rounded px-2 py-1.5 w-32 outline-none focus:border-emerald-500"
          />
          <input
            type="number"
            value={tagWeight}
            onChange={handleTagWeightChange}
            placeholder={t('bulkTag.weight')}
            className="text-xs bg-gray-800 border border-gray-600 rounded px-2 py-1.5 w-16 outline-none focus:border-emerald-500"
          />
          <button onClick={handleCreate} disabled={!canCreate} className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white disabled:opacity-50">
            {creating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
            {t('bulkTag.create')}
          </button>

          {createResult && (
            <span className="text-xs ml-2">
              <span className="text-emerald-400">{t('bulkTag.resultCreated', { count: createResult.created })}</span>
              {createResult.duplicates > 0 && (
                <span className="text-yellow-400 ml-2">{t('bulkTag.resultDuplicates', { count: createResult.duplicates })}</span>
              )}
            </span>
          )}
        </div>
      </div>

      {/* Section B: Unique Tags List */}
      <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
        <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
          <h2 className="text-lg font-bold flex items-center gap-2 text-gray-300">
            <List className="w-4 h-4 text-emerald-500" />
            {t('tags.title')}
          </h2>
          <div className="flex items-center gap-4">
            <button onClick={handlePrevPage} className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded" disabled={pagination.offset === 0}>
              {t('tags.prev')}
            </button>
            <span className="text-xs font-mono">
              {pagination.offset + 1} - {pagination.offset + tags.length}
            </span>
            <button onClick={handleNextPage} className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded" disabled={tags.length < pagination.limit}>
              {t('tags.next')}
            </button>
            <button onClick={fetchTags} className="p-1 hover:text-emerald-400" title={t('tags.refresh')}>
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        <div className="divide-y divide-gray-700">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
            </div>
          ) : tags.length === 0 ? (
            <div className="px-6 py-8 text-center text-xs text-gray-500 uppercase tracking-wide">
              {t('tags.noTags')}
            </div>
          ) : (
            tags.map((tg) => (
              <div key={tg.id}>
                <div className="px-6 py-3 flex items-center justify-between hover:bg-gray-700/30 transition-colors">
                  <div className="flex items-center gap-3">
                    <button onClick={() => toggleDetail(tg.id)} className="flex items-center gap-1 group">
                      {expandedTagId === tg.id
                        ? <ChevronDown className="w-3 h-3 text-gray-500" />
                        : <ChevronRight className="w-3 h-3 text-gray-500" />
                      }
                      <TagBadge name={tg.name} weight={tg.weight} />
                    </button>
                    <span className="text-[10px] text-gray-500">w:{tg.weight}</span>
                    <span className="text-[10px] text-gray-500">
                      ({t('tags.targetCount', { count: tg.target_count })})
                    </span>
                  </div>
                  <button onClick={() => handleDeleteTag(tg.id)} className="p-1 text-gray-500 hover:text-red-400">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                {/* Tag detail panel */}
                {expandedTagId === tg.id && (
                  <div className="px-6 py-3 bg-gray-900/60 border-t border-gray-700/50">
                    {loadingDetail ? (
                      <div className="flex items-center gap-2 py-2">
                        <Loader2 className="w-4 h-4 text-emerald-500 animate-spin" />
                        <span className="text-xs text-gray-500">{t('tags.loadingDetail')}</span>
                      </div>
                    ) : tagDetail ? (
                      <div>
                        {/* Tag-level weight */}
                        <div className="flex items-center gap-3 mb-3">
                          <span className="text-xs font-bold text-gray-400 uppercase">{t('tags.tagWeight')}</span>
                          {editingTagWeight != null ? (
                            <span className="flex items-center gap-1">
                              <input
                                type="number"
                                value={editingTagWeight}
                                onChange={handleTagWeightEditChange}
                                onKeyDown={handleTagWeightEditKeyDown}
                                className="text-xs bg-gray-800 border border-emerald-600 rounded px-2 py-0.5 w-16 outline-none"
                                autoFocus
                              />
                              <button onClick={handleSaveTagWeight} className="p-0.5 text-emerald-400 hover:text-emerald-300"><Check className="w-3 h-3" /></button>
                              <button onClick={handleCancelTagWeightEdit} className="p-0.5 text-gray-500 hover:text-gray-300"><X className="w-3 h-3" /></button>
                            </span>
                          ) : (
                            <button onClick={handleStartTagWeightEdit} className="text-xs font-mono text-emerald-400 hover:text-emerald-300 px-1.5 py-0.5 rounded bg-gray-800 hover:bg-gray-700">
                              {tagDetail.weight}
                            </button>
                          )}
                        </div>

                        {/* Targets list */}
                        {(() => {
                          const types = [...new Set(tagDetail.targets.map((tgt) => tgt.target_type))].sort();
                          const filtered = targetTypeFilter
                            ? tagDetail.targets.filter((tgt) => tgt.target_type === targetTypeFilter)
                            : tagDetail.targets;
                          return (
                            <>
                              <div className="flex items-center gap-2 mb-2 flex-wrap">
                                <span className="text-xs font-bold text-gray-400 uppercase">
                                  {t('tags.targets')} ({filtered.length}/{tagDetail.targets.length})
                                </span>
                                {types.length > 1 && (
                                  <div className="flex gap-1">
                                    <button
                                      onClick={() => setTargetTypeFilter(null)}
                                      className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded transition-colors ${!targetTypeFilter ? 'bg-emerald-700 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'}`}
                                    >
                                      {t('tags.filterAll')}
                                    </button>
                                    {types.map((type) => (
                                      <button
                                        key={type}
                                        onClick={() => setTargetTypeFilter(type)}
                                        className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded transition-colors ${targetTypeFilter === type ? 'bg-emerald-700 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'}`}
                                      >
                                        {type.replace('_', ' ')}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                              {filtered.length === 0 ? (
                                <div className="text-xs text-gray-500 py-1">{t('tags.noTargets')}</div>
                              ) : (
                                <div className="space-y-1">
                                  {filtered.map((tgt) => (
                                    <TagTargetRow
                                      key={tgt.id}
                                      tgt={tgt}
                                      editingWeight={editingTargetWeights[tgt.id] ?? null}
                                      onStartEdit={() => startTargetWeightEdit(tgt)}
                                      onSaveWeight={() => handleSaveTargetWeight(tgt.id)}
                                      onCancelEdit={() => cancelTargetWeightEdit(tgt.id)}
                                      onChangeWeight={(e) => changeTargetWeight(tgt.id, e)}
                                      onDelete={() => handleDeleteTarget(tgt.id)}
                                      t={t}
                                    />
                                  ))}
                                </div>
                              )}
                            </>
                          );
                        })()}
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
const ListingsPanel = () => {
  const { t } = useTranslation();
  const [listings, setListings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });
  const [expandedListingIds, setExpandedListingIds] = useState({});
  const [detailByListing, setDetailByListing] = useState({});
  const [loadingDetail, setLoadingDetail] = useState({});

  const fetchListings = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await getListings({ limit: pagination.limit, offset: pagination.offset });
      setListings(data.rows || []);
    } catch (error) {
      console.error('Error fetching listings:', error);
      setListings([]);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.offset, pagination.limit]);

  useEffect(() => {
    fetchListings();
  }, [fetchListings]);

  const fetchListingDetail = async (listingId) => {
    if (detailByListing[listingId] || loadingDetail[listingId]) return;
    setLoadingDetail((prev) => ({ ...prev, [listingId]: true }));
    try {
      const { data } = await getListingDetail(listingId);
      setDetailByListing((prev) => ({ ...prev, [listingId]: data }));
    } catch (error) {
      console.error(`Error fetching listing detail ${listingId}:`, error);
      setDetailByListing((prev) => ({ ...prev, [listingId]: { enchants: [], reforge_options: [] } }));
    } finally {
      setLoadingDetail((prev) => ({ ...prev, [listingId]: false }));
    }
  };

  const toggleListing = (id) => {
    setExpandedListingIds((prev) => ({ ...prev, [id]: !prev[id] }));
    fetchListingDetail(id);
  };

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
      <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Package className="w-5 h-5 text-cyan-500" />
          {t('listings.title')}
        </h2>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={pagination.offset === 0}
          >
            {t('listings.prev')}
          </button>
          <span className="text-xs font-mono">
            {pagination.offset + 1} - {pagination.offset + listings.length}
          </span>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={listings.length < pagination.limit}
          >
            {t('listings.next')}
          </button>
          <button onClick={fetchListings} className="p-1 hover:text-cyan-400" title={t('listings.refresh')}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="divide-y divide-gray-700">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
          </div>
        ) : listings.length === 0 ? (
          <div className="px-6 py-8 text-center text-xs text-gray-500 uppercase tracking-wide">
            {t('listings.noListings')}
          </div>
        ) : (
          listings.map((listing) => {
            const isExpanded = !!expandedListingIds[listing.id];
            const detail = detailByListing[listing.id];
            const isDetailLoading = !!loadingDetail[listing.id];

            return (
              <div key={listing.id} className="transition-colors hover:bg-gray-700/30">
                <div
                  className="px-6 py-4 flex items-center justify-between cursor-pointer"
                  onClick={() => toggleListing(listing.id)}
                >
                  <div className="flex items-center gap-4">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-cyan-500" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-500" />
                    )}
                    <span className="text-lg font-black text-white">{listing.name || t('listings.unnamed')}</span>
                    {listing.prefix_enchant_name && (
                      <span className="text-xs font-bold text-blue-400 uppercase tracking-tighter">
                        {listing.prefix_enchant_name}
                      </span>
                    )}
                    {listing.suffix_enchant_name && (
                      <span className="text-xs font-bold text-red-400 uppercase tracking-tighter">
                        {listing.suffix_enchant_name}
                      </span>
                    )}
                    {listing.game_item_name && (
                      <span className="text-xs text-gray-400">
                        {listing.game_item_name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4">
                    {listing.price != null && (
                      <span className="text-sm font-bold text-yellow-400">
                        {t('listings.price', { price: Number(listing.price).toLocaleString() })}
                      </span>
                    )}
                    {listing.created_at && (
                      <span className="text-[10px] font-mono text-gray-500">
                        {new Date(listing.created_at).toLocaleString()}
                      </span>
                    )}
                    <span className="text-[10px] font-mono text-gray-500 bg-black/30 px-2 py-0.5 rounded">
                      ID: {listing.id}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-16 py-4 bg-black/20 space-y-4">
                    {isDetailLoading ? (
                      <div className="py-4 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin text-gray-600" />
                          <span className="text-xs text-gray-600 uppercase">{t('listings.loadingDetails')}</span>
                        </div>
                      </div>
                    ) : detail ? (
                      <>
                        {(detail.item_type || detail.item_grade) && (
                          <div className="mb-3">
                            <p className="text-xs text-gray-400">
                              {[detail.item_type, detail.item_grade].filter(Boolean).join(' / ')}
                            </p>
                          </div>
                        )}

                        {(detail.erg_grade || detail.special_upgrade_type) && (
                          <div className="mb-3 flex flex-wrap gap-2">
                            {detail.erg_grade && (
                              <span className="text-xs px-2 py-1 bg-yellow-900/40 text-yellow-300 rounded">
                                ERG {detail.erg_grade}{detail.erg_level != null ? ` Lv.${detail.erg_level}` : ''}
                              </span>
                            )}
                            {detail.special_upgrade_type && (
                              <span className={`text-xs px-2 py-1 rounded ${detail.special_upgrade_type === 'R' ? 'bg-pink-900/40 text-pink-300' : 'bg-cyan-900/40 text-cyan-300'}`}>
                                {detail.special_upgrade_type}강{detail.special_upgrade_level != null ? ` Lv.${detail.special_upgrade_level}` : ''}
                              </span>
                            )}
                          </div>
                        )}

                        {(() => {
                          const attrs = Object.entries(ATTR_LABELS).filter(([k]) => detail[k] != null);
                          if (!attrs.length) return null;
                          return (
                            <div className="mb-3">
                              <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1 mb-2">
                                아이템 속성
                              </p>
                              <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                                {attrs.map(([k, label]) => (
                                  <div key={k} className="flex justify-between text-xs">
                                    <span className="text-gray-500">{label}</span>
                                    <span className="text-gray-300">{detail[k]}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })()}

                        {(detail.prefix_enchant || detail.suffix_enchant) && (
                          <div className="space-y-3">
                            <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1">
                              {t('listings.enchants')}
                            </p>
                            {[detail.prefix_enchant, detail.suffix_enchant].filter(Boolean).map((enc, idx) => (
                              <div key={idx} className="bg-gray-800/50 p-3 rounded-lg border border-gray-700/50">
                                <div className="flex items-center gap-3 mb-2">
                                  <span className={`text-xs font-bold uppercase px-1.5 py-0.5 rounded ${
                                    enc.slot === 0 ? 'bg-blue-900/50 text-blue-300' : 'bg-red-900/50 text-red-300'
                                  }`}>
                                    {enc.slot === 0 ? t('listings.prefix') : t('listings.suffix')}
                                  </span>
                                  <span className="text-sm font-bold text-white">{enc.enchant_name}</span>
                                  <span className="text-xs text-gray-500">{t('listings.rank', { rank: toRankLabel(enc.rank) })}</span>
                                </div>
                                {enc.effects?.length > 0 && (
                                  <ul className="space-y-1 ml-4">
                                    {enc.effects.map((eff, effIdx) => (
                                      <li key={effIdx} className="flex items-center gap-2">
                                        <span className="text-sm text-gray-300">{eff.raw_text}</span>
                                        {eff.value != null ? (
                                          <span className="text-xs font-bold text-cyan-400">
                                            = {eff.value}
                                          </span>
                                        ) : eff.min_value != null && (
                                          <span className="text-xs text-gray-500">
                                            = {eff.min_value === eff.max_value ? eff.min_value : `${eff.min_value}~${eff.max_value}`}
                                          </span>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {detail.reforge_options?.length > 0 && (
                          <div className="space-y-3">
                            <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1">
                              {t('listings.reforgeOptions')}
                            </p>
                            <ul className="space-y-2">
                              {detail.reforge_options.map((opt, idx) => (
                                <li key={idx} className="bg-gray-800/50 p-3 rounded-lg border border-gray-700/50 flex items-center justify-between">
                                  <span className="text-sm font-medium text-gray-300">{opt.option_name}</span>
                                  <div className="flex items-center gap-2">
                                    {opt.level != null && (
                                      <span className="text-xs font-bold text-orange-400">
                                        {t('listings.level', { level: opt.level })}
                                      </span>
                                    )}
                                    {opt.max_level != null && (
                                      <span className="text-[10px] text-gray-500">
                                        / {opt.max_level}
                                      </span>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {detail.tags?.length > 0 && (
                          <div className="mb-3 flex flex-wrap gap-2">
                            {detail.tags.map((tag, idx) => {
                              const c = getTagColor(tag.weight);
                              return (
                                <span key={idx} className={`text-xs font-bold px-2 py-0.5 rounded ${c.bg} ${c.text}`}>
                                  {tag.name}
                                </span>
                              );
                            })}
                          </div>
                        )}

                        {(!detail.prefix_enchant && !detail.suffix_enchant && !detail.reforge_options?.length) && (
                          <p className="text-xs text-gray-600 uppercase">{t('listings.noEnchantReforge')}</p>
                        )}
                      </>
                    ) : null}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

const VALID_TABS = ['enchants', 'listings', 'corrections', 'tags'];

const Admin = () => {
  const { t } = useTranslation();
  const { tab } = useParams();
  const activeTab = VALID_TABS.includes(tab) ? tab : null;
  const [summary, setSummary] = useState(null);
  const [entries, setEntries] = useState([]);
  const [effectsByEnchant, setEffectsByEnchant] = useState({});
  const [loadingEffects, setLoadingEffects] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [expandedEnchantIds, setExpandedEnchantIds] = useState({});
  const [nameQuery, setNameQuery] = useState('');
  const [pagination, setPagination] = useState({ limit: 100, offset: 0 });

  const TABS = useMemo(() => [
    { key: 'enchants', label: t('tabs.enchants') },
    { key: 'listings', label: t('tabs.listings') },
    { key: 'corrections', label: t('tabs.corrections') },
    { key: 'tags', label: t('tabs.tags') },
  ], [t]);

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
              {t('admin.title')} <span className="text-cyan-500">{t('admin.titleHighlight')}</span>
            </h1>
            <p className="text-gray-400 text-sm mt-1">{t('admin.subtitle')}</p>
          </div>
          {summary && (
            <div className="flex gap-4">
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">{t('stats.enchants')}</span>
                <span className="text-lg font-bold text-cyan-400">{stats.enchants}</span>
              </div>
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">{t('stats.effects')}</span>
                <span className="text-lg font-bold text-cyan-400">{stats.effects}</span>
              </div>
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">{t('stats.enchantEffects')}</span>
                <span className="text-lg font-bold text-cyan-400">{stats.enchantEffects}</span>
              </div>
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">{t('stats.listings')}</span>
                <span className="text-lg font-bold text-cyan-400">{stats.listings}</span>
              </div>
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">{t('stats.gameItems')}</span>
                <span className="text-lg font-bold text-cyan-400">{stats.gameItems}</span>
              </div>
              <div className="bg-gray-800 px-4 py-2 rounded-lg border border-gray-700">
                <span className="text-[10px] font-black text-gray-500 block uppercase">{t('stats.tags')}</span>
                <span className="text-lg font-bold text-emerald-400">{stats.tags}</span>
              </div>
            </div>
          )}
        </header>

        <nav className="flex gap-1 mb-6">
          {TABS.map((tb) => (
            <Link
              key={tb.key}
              to={`/${tb.key}`}
              className={`px-5 py-2 text-sm font-bold uppercase tracking-wide rounded-t-lg border border-b-0 ${
                activeTab === tb.key
                  ? 'bg-gray-800 text-cyan-400 border-gray-700'
                  : 'bg-gray-900 text-gray-500 border-gray-800 hover:text-gray-300'
              }`}
            >
              {tb.label}
            </Link>
          ))}
        </nav>

        {!activeTab ? null : activeTab === 'corrections' ? (
          <CorrectionsPanel />
        ) : activeTab === 'listings' ? (
          <ListingsPanel />
        ) : activeTab === 'tags' ? (
          <TagsPanel />
        ) : isLoading && !summary ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-12 h-12 text-cyan-500 animate-spin mb-4" />
            <p className="text-gray-400 font-bold tracking-widest uppercase">{t('admin.initializing')}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-8">
            <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
              <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <List className="w-5 h-5 text-cyan-500" />
                  {t('enchants.title')}
                </h2>
                <div className="flex items-center gap-4">
                  <input
                    type="text"
                    value={nameQuery}
                    onChange={(e) => setNameQuery(e.target.value)}
                    placeholder={t('enchants.searchPlaceholder')}
                    className="text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1 outline-none focus:border-cyan-500"
                  />
                  <button
                    onClick={() => {
                      setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }));
                    }}
                    className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
                    disabled={pagination.offset === 0}
                  >
                    {t('enchants.prev')}
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
                    {t('enchants.next')}
                  </button>
                  <button onClick={fetchInitialData} className="p-1 hover:text-cyan-400" title={t('enchants.refresh')}>
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
                                toSlotLabel(entry.slot, t) === t('enchants.prefix')
                                  ? 'bg-blue-900/50 text-blue-300'
                                  : 'bg-red-900/50 text-red-300'
                              }`}
                            >
                              {toSlotLabel(entry.slot, t)}
                            </span>
                            <span className="text-lg font-black text-white">{entry.name}</span>
                            <span className="ml-3 text-sm text-gray-500">{t('enchants.rank', { rank: toRankLabel(entry.rank) })}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className="text-[10px] font-mono text-gray-500 bg-black/30 px-2 py-0.5 rounded">
                            ID: {entry.id}
                          </span>
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
                                        {Number(eff.effect_direction) === 0 ? t('enchants.increase') : t('enchants.decrease')}
                                      </span>
                                    )}
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
                                    {eff.effect_value != null && (
                                      <span className={`text-[10px] ${getEffectToneClass(eff)}`}>{t('enchants.value', { value: eff.effect_value })}</span>
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
                {filteredEntries.length === 0 && (
                  <div className="px-6 py-8 text-center text-xs text-gray-500 uppercase tracking-wide">
                    {t('enchants.noMatch')}
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
