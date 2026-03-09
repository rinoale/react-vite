import React, { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Loader2, ChevronDown, ChevronRight, List, RefreshCw, Check, X, Plus, Search, Tag, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getTags, createTag, deleteTag, searchTagEntities, bulkCreateTags, getUniqueTags, deleteTagById, getTagDetail, updateTagWeight, updateTagTargetWeight, bulkUpdateTagTargetWeights } from '@mabi/shared/api/admin';
import CustomSelect from '@mabi/shared/components/CustomSelect';
import TagBadge from '@mabi/shared/components/TagBadge';
import { getTagColor } from '@mabi/shared/lib/tagColors';
import { pillActive, pillInactive, btnSmEmerald, weightInputSm } from '@mabi/shared/styles';

const ENTITY_TYPES = [
  { value: 'reforge_options', label: 'Reforge Option' },
  { value: 'echostone_options', label: 'Echostone Option' },
  { value: 'murias_relic_options', label: 'Murias Relic Option' },
  { value: 'game_item', label: 'Game Item' },
  { value: 'listing', label: 'Listing' },
  { value: 'enchant', label: 'Enchant' },
];

const AdminTagBadge = ({ name, weight }) => (
  <TagBadge name={name} weight={weight} size="sm" className="group-hover:ring-1 ring-emerald-500/50" />
);

const TagTargetRow = ({ tgt, editingWeight, onStartEdit, onSaveWeight, onCancelEdit, onChangeWeight, onDelete, t }) => {
  const weightColor = getTagColor(editingWeight != null ? (parseInt(editingWeight, 10) || 0) : tgt.weight);
  return (
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
            className={`text-xs font-bold bg-gray-800 border border-emerald-600 rounded px-1.5 py-0.5 w-14 outline-none ${weightColor.text}`}
            autoFocus
          />
          <button onClick={onSaveWeight} className="p-0.5 text-emerald-400 hover:text-emerald-300"><Check className="w-3 h-3" /></button>
          <button onClick={onCancelEdit} className="p-0.5 text-gray-500 hover:text-gray-300"><X className="w-3 h-3" /></button>
        </span>
      ) : (
        <button onClick={onStartEdit} className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-gray-800 hover:bg-gray-700 ${weightColor.text}`}>
          {tgt.weight}
        </button>
      )}
      <button onClick={onDelete} className="p-0.5 text-gray-500 hover:text-red-400">
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};

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
  const [tagWeight, setTagWeight] = useState('');
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
  const [bulkWeight, setBulkWeight] = useState('');

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

  const handleSearchTypeChange = useCallback((val) => setSearchType(val), []);
  const handleLikeChange = useCallback((e) => setLikeSearch(e.target.checked), []);
  const handleTagNameChange = useCallback((e) => setTagName(e.target.value), []);
  const handleTagWeightChange = useCallback((e) => setTagWeight(e.target.value), []);

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
        weight: parseInt(tagWeight, 10) || 0,
      });
      setCreateResult(data);
      if (data.created > 0) {
        setSelectedTargets([]);
        setTagName('');
        setTagWeight('');
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
    const w = parseInt(editingTagWeight, 10) || 0;
    try {
      await updateTagWeight(tagDetail.id, w);
      setTagDetail((prev) => ({ ...prev, weight: w }));
      setEditingTagWeight(null);
      fetchTags();
    } catch (error) {
      console.error('Error updating tag weight:', error);
    }
  }, [editingTagWeight, tagDetail, fetchTags]);

  const handleCancelTagWeightEdit = useCallback(() => setEditingTagWeight(null), []);
  const handleStartTagWeightEdit = useCallback(() => setEditingTagWeight(String(tagDetail?.weight ?? 0)), [tagDetail]);
  const handleTagWeightEditChange = useCallback((e) => setEditingTagWeight(e.target.value), []);

  const handleTagWeightEditKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleSaveTagWeight();
    if (e.key === 'Escape') handleCancelTagWeightEdit();
  }, [handleSaveTagWeight, handleCancelTagWeightEdit]);

  const handleSaveTargetWeight = useCallback(async (ttId) => {
    const raw = editingTargetWeights[ttId];
    if (raw == null) return;
    const w = parseInt(raw, 10) || 0;
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
    setEditingTargetWeights((prev) => ({ ...prev, [tgt.id]: String(tgt.weight) }));
  }, []);

  const cancelTargetWeightEdit = useCallback((ttId) => {
    setEditingTargetWeights((prev) => { const n = { ...prev }; delete n[ttId]; return n; });
  }, []);

  const changeTargetWeight = useCallback((ttId, e) => {
    setEditingTargetWeights((prev) => ({ ...prev, [ttId]: e.target.value }));
  }, []);

  const handleBulkWeightUpdate = useCallback(async () => {
    if (!tagDetail || bulkWeight === '') return;
    const w = parseInt(bulkWeight, 10) || 0;
    const filtered = targetTypeFilter
      ? tagDetail.targets.filter((tgt) => tgt.target_type === targetTypeFilter)
      : tagDetail.targets;
    if (filtered.length === 0) return;
    const ids = filtered.map((tgt) => tgt.id);
    try {
      await bulkUpdateTagTargetWeights(ids, w);
      setTagDetail((prev) => ({
        ...prev,
        targets: prev.targets.map((tgt) => ids.includes(tgt.id) ? { ...tgt, weight: w } : tgt),
      }));
      setBulkWeight('');
    } catch (error) {
      console.error('Error bulk updating target weights:', error);
    }
  }, [tagDetail, targetTypeFilter, bulkWeight]);

  const handleBulkWeightKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleBulkWeightUpdate();
  }, [handleBulkWeightUpdate]);

  const canCreate = !creating && tagName.trim().length > 0;

  return (
    <div className="space-y-6">
      {/* Section A: Bulk Tag Creator */}
      <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl">
        <div className="bg-gray-700/50 px-6 py-4 rounded-t-2xl">
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
              <div className="absolute z-50 mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-48 overflow-auto scrollbar-thin">
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
            className={`text-xs font-bold bg-gray-800 border border-gray-600 rounded px-2 py-1.5 w-16 outline-none focus:border-emerald-500 ${getTagColor(parseInt(tagWeight, 10) || 0).text}`}
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

        {/* Color tier legend */}
        <div className="px-6 py-3 border-t border-gray-700 flex flex-wrap gap-2">
          {[
            { label: '80+ Artifact', w: 80 },
            { label: '70+ Mythic', w: 70 },
            { label: '60+ Legendary', w: 60 },
            { label: '50+ Heroic', w: 50 },
            { label: '40+ Epic', w: 40 },
            { label: '30+ Rare', w: 30 },
            { label: '20+ Uncommon', w: 20 },
            { label: '10+ Common', w: 10 },
            { label: '0+ Hidden', w: 0 },
          ].map(({ label, w }) => {
            const c = getTagColor(w);
            return (
              <span key={w} className={`text-[10px] px-1.5 py-0.5 rounded border ${c.bg} ${c.text} ${c.border}`}>
                {label}
              </span>
            );
          })}
        </div>
      </div>

      {/* Section B: Unique Tags List */}
      <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl">
        <div className="bg-gray-700/50 px-6 py-4 rounded-t-2xl flex justify-between items-center">
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
                      <AdminTagBadge name={tg.name} weight={tg.weight} />
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
                        {(() => {
                          const twc = getTagColor(editingTagWeight != null ? (parseInt(editingTagWeight, 10) || 0) : tagDetail.weight);
                          return (
                        <div className="flex items-center gap-3 mb-3">
                          <span className="text-xs font-bold text-gray-400 uppercase">{t('tags.tagWeight')}</span>
                          {editingTagWeight != null ? (
                            <span className="flex items-center gap-1">
                              <input
                                type="number"
                                value={editingTagWeight}
                                onChange={handleTagWeightEditChange}
                                onKeyDown={handleTagWeightEditKeyDown}
                                className={`text-xs font-bold bg-gray-800 border border-emerald-600 rounded px-2 py-0.5 w-16 outline-none ${twc.text}`}
                                autoFocus
                              />
                              <button onClick={handleSaveTagWeight} className="p-0.5 text-emerald-400 hover:text-emerald-300"><Check className="w-3 h-3" /></button>
                              <button onClick={handleCancelTagWeightEdit} className="p-0.5 text-gray-500 hover:text-gray-300"><X className="w-3 h-3" /></button>
                            </span>
                          ) : (
                            <button onClick={handleStartTagWeightEdit} className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded bg-gray-800 hover:bg-gray-700 ${twc.text}`}>
                              {tagDetail.weight}
                            </button>
                          )}
                        </div>
                          );
                        })()}

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
                                      className={!targetTypeFilter ? pillActive : pillInactive}
                                    >
                                      {t('tags.filterAll')}
                                    </button>
                                    {types.map((type) => (
                                      <button
                                        key={type}
                                        onClick={() => setTargetTypeFilter(type)}
                                        className={targetTypeFilter === type ? pillActive : pillInactive}
                                      >
                                        {type.replace('_', ' ')}
                                      </button>
                                    ))}
                                  </div>
                                )}
                                <div className="flex items-center gap-1 ml-auto">
                                  <input
                                    type="number"
                                    value={bulkWeight}
                                    onChange={(e) => setBulkWeight(e.target.value)}
                                    onKeyDown={handleBulkWeightKeyDown}
                                    placeholder="w"
                                    className={`${weightInputSm} ${getTagColor(parseInt(bulkWeight, 10) || 0).text}`}
                                  />
                                  <button
                                    onClick={handleBulkWeightUpdate}
                                    disabled={bulkWeight === '' || filtered.length === 0}
                                    className={btnSmEmerald}
                                  >
                                    {t('tags.bulkUpdate', { count: filtered.length })}
                                  </button>
                                </div>
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

export default TagsPanel;
