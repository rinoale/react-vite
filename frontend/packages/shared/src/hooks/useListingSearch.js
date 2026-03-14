import { useState, useRef, useEffect, useCallback } from 'react';
import { searchListings, searchTags } from '../api/listings';
import { searchTypedItems } from '../lib/gameItems';

/**
 * Shared search logic for tag-chip + game-item + text listing search.
 *
 * @param {Object} options
 * @param {function} options.onResults - called with listing results array
 * @param {function} options.onSelectListing - called when a listing suggestion is clicked
 * @param {function} options.onSubmit - called on Enter/submit with ({ tags, text, gameItem }). If provided, replaces default executeSearch.
 * @param {function} options.onClear - called after search state is cleared
 * @param {number}   options.debounceMs - debounce delay (default 200)
 */
export function useListingSearch({ onResults, onSelectListing, onSubmit, onClear, debounceMs = 200 } = {}) {
  const [searchText, setSearchText] = useState('');
  const [selectedTags, setSelectedTags] = useState([]);
  const [tagWeights, setTagWeights] = useState({});
  const [selectedGameItem, setSelectedGameItem] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [focusIdx, setFocusIdx] = useState(-1);
  const [attrFilters, setAttrFilters] = useState([]);
  const [reforgeFilters, setReforgeFilters] = useState([]);
  const [enchantFilters, setEnchantFilters] = useState([]);
  const [echostoneFilters, setEchostoneFilters] = useState([]);
  const [muriasFilters, setMuriasFilters] = useState([]);

  const debounceRef = useRef(null);
  const containerRef = useRef(null);
  const inputRef = useRef(null);
  const attrFiltersRef = useRef([]);
  const reforgeFiltersRef = useRef([]);
  const enchantFiltersRef = useRef([]);
  const echostoneFiltersRef = useRef([]);
  const muriasFiltersRef = useRef([]);

  // --- Close on outside click ---
  useEffect(() => {
    if (!showSuggestions) return;
    const handleClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showSuggestions]);

  // --- Cleanup debounce ---
  useEffect(() => () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
  }, []);

  // --- Execute search ---
  const executeSearch = useCallback(async (tags, text, gameItem) => {
    const validAttr = attrFiltersRef.current.filter((f) => f.key && ((f.value !== '' && f.value != null) || f.grade || f.type));
    const validReforge = reforgeFiltersRef.current.filter((f) => f.option_name);
    const validEnchant = enchantFiltersRef.current.filter((f) => f.name);
    const validEchostone = echostoneFiltersRef.current.filter((f) => f.option_name);
    const validMurias = muriasFiltersRef.current.filter((f) => f.option_name);
    try {
      const { data } = await searchListings(
        text?.trim() || '',
        tags.length > 0 ? tags : undefined,
        {
          gameItemId: gameItem?.id,
          ...(validAttr.length ? { attrFilters: validAttr } : {}),
          ...(validReforge.length ? { reforgeFilters: validReforge } : {}),
          ...(validEnchant.length ? { enchantFilters: validEnchant } : {}),
          ...(validEchostone.length ? { echostoneFilters: validEchostone } : {}),
          ...(validMurias.length ? { muriasFilters: validMurias } : {}),
        },
      );
      onResults?.(data, {
        tags, text: text?.trim() || '', gameItem,
        attrFilters: validAttr, reforgeFilters: validReforge, enchantFilters: validEnchant,
        echostoneFilters: validEchostone, muriasFilters: validMurias,
      });
    } catch (error) {
      console.error('Search failed:', error);
    }
  }, [onResults]);

  // --- Fetch suggestions (tags + game items + listings) ---
  const fetchSuggestions = useCallback(async (text) => {
    if (!text.trim()) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    try {
      const gameItems = searchTypedItems(text.trim(), 3);
      const [{ data: tags }, { data: listings }] = await Promise.all([
        searchTags(text.trim()),
        searchListings(text.trim()),
      ]);
      const items = [
        ...tags.map((tg) => ({
          type: 'tag',
          value: tg.name,
          label: tg.name,
          weight: tg.weight,
        })),
        ...gameItems.map((gi) => ({
          type: 'game_item',
          value: gi.id,
          label: gi.name,
          data: gi,
        })),
        ...listings.map((l) => ({
          type: 'listing',
          value: l.id,
          label: l.name,
          data: l,
        })),
      ];
      setSuggestions(items);
      setShowSuggestions(items.length > 0);
      setFocusIdx(items.length > 0 ? 0 : -1);
    } catch {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, []);

  // --- Text input change ---
  const handleTextChange = useCallback((e) => {
    const val = e.target.value;
    setSearchText(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(val), debounceMs);
  }, [fetchSuggestions, debounceMs]);

  // --- Select tag ---
  const handleSelectTag = useCallback((tagName, weight) => {
    setSelectedTags((prev) => {
      if (prev.includes(tagName)) return prev;
      const next = [...prev, tagName];
      executeSearch(next, '', selectedGameItem);
      return next;
    });
    if (weight != null) setTagWeights((prev) => ({ ...prev, [tagName]: weight }));
    setSearchText('');
    setSuggestions([]);
    setShowSuggestions(false);
    inputRef.current?.focus();
  }, [executeSearch, selectedGameItem]);

  // --- Select game item ---
  const handleSelectGameItem = useCallback((gameItem) => {
    setSelectedGameItem(gameItem);
    // Clear filters that don't apply to new item type
    attrFiltersRef.current = [];
    setAttrFilters([]);
    reforgeFiltersRef.current = [];
    setReforgeFilters([]);
    enchantFiltersRef.current = [];
    setEnchantFilters([]);
    echostoneFiltersRef.current = [];
    setEchostoneFilters([]);
    muriasFiltersRef.current = [];
    setMuriasFilters([]);
    executeSearch(selectedTags, '', gameItem);
    setSearchText('');
    setSuggestions([]);
    setShowSuggestions(false);
    inputRef.current?.focus();
  }, [executeSearch, selectedTags]);

  // --- Remove game item ---
  const handleRemoveGameItem = useCallback(() => {
    setSelectedGameItem(null);
    attrFiltersRef.current = [];
    setAttrFilters([]);
    reforgeFiltersRef.current = [];
    setReforgeFilters([]);
    enchantFiltersRef.current = [];
    setEnchantFilters([]);
    echostoneFiltersRef.current = [];
    setEchostoneFilters([]);
    muriasFiltersRef.current = [];
    setMuriasFilters([]);
    executeSearch(selectedTags, searchText, null);
  }, [executeSearch, selectedTags, searchText]);

  // --- Select suggestion item (tag, game_item, or listing) ---
  const handleSelectItem = useCallback((item) => {
    if (item.type === 'tag') {
      handleSelectTag(item.value, item.weight);
    } else if (item.type === 'game_item') {
      handleSelectGameItem(item.data);
    } else {
      onSelectListing?.(item.data);
      setSearchText('');
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, [handleSelectTag, handleSelectGameItem, onSelectListing]);

  // --- Remove tag ---
  const handleRemoveTag = useCallback((tagName) => {
    setSelectedTags((prev) => {
      const next = prev.filter((t) => t !== tagName);
      executeSearch(next, searchText, selectedGameItem);
      return next;
    });
    setTagWeights((prev) => { const n = { ...prev }; delete n[tagName]; return n; });
  }, [executeSearch, searchText, selectedGameItem]);

  // --- Serialize all search state to a plain JSON-safe object ---
  const toSearchParams = useCallback(() => ({
    text: searchText,
    tags: selectedTags,
    tagWeights,
    gameItem: selectedGameItem,
    attrFilters: attrFiltersRef.current,
    reforgeFilters: reforgeFiltersRef.current,
    enchantFilters: enchantFiltersRef.current,
    echostoneFilters: echostoneFiltersRef.current,
    muriasFilters: muriasFiltersRef.current,
  }), [searchText, selectedTags, tagWeights, selectedGameItem]);

  // --- Submit search (Enter / button) ---
  const handleSubmitSearch = useCallback(() => {
    setShowSuggestions(false);
    if (onSubmit) {
      onSubmit(toSearchParams());
    } else {
      executeSearch(selectedTags, searchText, selectedGameItem);
    }
  }, [selectedTags, searchText, selectedGameItem, executeSearch, onSubmit, toSearchParams]);

  // --- Attribute filter CRUD ---
  const handleAddAttrFilter = useCallback((key) => {
    const extra = {};
    if (key === 'erg_level') extra.grade = '';
    if (key === 'special_upgrade_level') extra.type = '';
    const next = [...attrFiltersRef.current, { key, op: 'gte', value: '', ...extra }];
    attrFiltersRef.current = next;
    setAttrFilters(next);
  }, []);

  const handleUpdateAttrFilter = useCallback((index, updates) => {
    const next = attrFiltersRef.current.map((f, i) => (i === index ? { ...f, ...updates } : f));
    attrFiltersRef.current = next;
    setAttrFilters(next);
  }, []);

  const handleRemoveAttrFilter = useCallback((index) => {
    const next = attrFiltersRef.current.filter((_, i) => i !== index);
    attrFiltersRef.current = next;
    setAttrFilters(next);
  }, []);

  // --- Reforge filter CRUD ---
  const handleAddReforgeFilter = useCallback((filter) => {
    const next = [...reforgeFiltersRef.current, filter];
    reforgeFiltersRef.current = next;
    setReforgeFilters(next);
  }, []);

  const handleUpdateReforgeFilter = useCallback((index, updates) => {
    const next = reforgeFiltersRef.current.map((f, i) => (i === index ? { ...f, ...updates } : f));
    reforgeFiltersRef.current = next;
    setReforgeFilters(next);
  }, []);

  const handleRemoveReforgeFilter = useCallback((index) => {
    const next = reforgeFiltersRef.current.filter((_, i) => i !== index);
    reforgeFiltersRef.current = next;
    setReforgeFilters(next);
  }, []);

  // --- Enchant filter CRUD ---
  const handleAddEnchantFilter = useCallback((filter) => {
    const next = [...enchantFiltersRef.current, filter];
    enchantFiltersRef.current = next;
    setEnchantFilters(next);
  }, []);

  const handleRemoveEnchantFilter = useCallback((index) => {
    const next = enchantFiltersRef.current.filter((_, i) => i !== index);
    enchantFiltersRef.current = next;
    setEnchantFilters(next);
  }, []);

  const handleUpdateEnchantEffect = useCallback((enchantIdx, effectIdx, updates) => {
    const next = enchantFiltersRef.current.map((f, i) => {
      if (i !== enchantIdx) return f;
      const effectFilters = f.effectFilters.map((ef, j) => (j === effectIdx ? { ...ef, ...updates } : ef));
      return { ...f, effectFilters };
    });
    enchantFiltersRef.current = next;
    setEnchantFilters(next);
  }, []);

  // --- Echostone filter CRUD ---
  const handleAddEchostoneFilter = useCallback((filter) => {
    const next = [...echostoneFiltersRef.current, filter];
    echostoneFiltersRef.current = next;
    setEchostoneFilters(next);
  }, []);

  const handleUpdateEchostoneFilter = useCallback((index, updates) => {
    const next = echostoneFiltersRef.current.map((f, i) => (i === index ? { ...f, ...updates } : f));
    echostoneFiltersRef.current = next;
    setEchostoneFilters(next);
  }, []);

  const handleRemoveEchostoneFilter = useCallback((index) => {
    const next = echostoneFiltersRef.current.filter((_, i) => i !== index);
    echostoneFiltersRef.current = next;
    setEchostoneFilters(next);
  }, []);

  // --- Murias filter CRUD ---
  const handleAddMuriasFilter = useCallback((filter) => {
    const next = [...muriasFiltersRef.current, filter];
    muriasFiltersRef.current = next;
    setMuriasFilters(next);
  }, []);

  const handleUpdateMuriasFilter = useCallback((index, updates) => {
    const next = muriasFiltersRef.current.map((f, i) => (i === index ? { ...f, ...updates } : f));
    muriasFiltersRef.current = next;
    setMuriasFilters(next);
  }, []);

  const handleRemoveMuriasFilter = useCallback((index) => {
    const next = muriasFiltersRef.current.filter((_, i) => i !== index);
    muriasFiltersRef.current = next;
    setMuriasFilters(next);
  }, []);

  // --- Clear all ---
  const handleClear = useCallback(() => {
    setSearchText('');
    setSelectedTags([]);
    setTagWeights({});
    setSelectedGameItem(null);
    setSuggestions([]);
    setShowSuggestions(false);
    attrFiltersRef.current = [];
    setAttrFilters([]);
    reforgeFiltersRef.current = [];
    setReforgeFilters([]);
    enchantFiltersRef.current = [];
    setEnchantFilters([]);
    echostoneFiltersRef.current = [];
    setEchostoneFilters([]);
    muriasFiltersRef.current = [];
    setMuriasFilters([]);
    onClear?.();
  }, [onClear]);

  // --- Keyboard nav ---
  const handleKeyDown = useCallback((e) => {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setFocusIdx((prev) => Math.min(prev + 1, suggestions.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setFocusIdx((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        if (focusIdx >= 0 && focusIdx < suggestions.length) {
          handleSelectItem(suggestions[focusIdx]);
        } else {
          handleSubmitSearch();
        }
        return;
      }
      if (e.key === 'Escape') {
        setShowSuggestions(false);
        return;
      }
    }
    if (e.key === 'Enter') {
      handleSubmitSearch();
      return;
    }
    if (e.key === 'Backspace' && !searchText) {
      if (selectedTags.length > 0) {
        handleRemoveTag(selectedTags[selectedTags.length - 1]);
      } else if (selectedGameItem) {
        handleRemoveGameItem();
      }
    }
  }, [showSuggestions, suggestions, focusIdx, searchText, selectedTags, selectedGameItem, handleSelectItem, handleSubmitSearch, handleRemoveTag, handleRemoveGameItem]);

  // --- Focus handler ---
  const handleInputFocus = useCallback(() => {
    if (suggestions.length > 0) setShowSuggestions(true);
  }, [suggestions]);

  const hasFilters = selectedTags.length > 0 || selectedGameItem != null || searchText.trim().length > 0
    || attrFilters.some((f) => (f.value !== '' && f.value != null) || f.grade || f.type)
    || reforgeFilters.length > 0
    || enchantFilters.length > 0
    || echostoneFilters.length > 0
    || muriasFilters.length > 0;

  // --- Restore search state from a params object and execute search ---
  const loadSearchParams = useCallback((params) => {
    if (!params) return;
    const text = params.text || '';
    const tags = params.tags || [];
    const weights = params.tagWeights || {};
    const gameItem = params.gameItem || null;
    const af = params.attrFilters || [];
    const rf = params.reforgeFilters || [];
    const ef = params.enchantFilters || [];
    const ecf = params.echostoneFilters || [];
    const mf = params.muriasFilters || [];

    setSearchText(text);
    setSelectedTags(tags);
    setTagWeights(weights);
    setSelectedGameItem(gameItem);
    attrFiltersRef.current = af;
    setAttrFilters(af);
    reforgeFiltersRef.current = rf;
    setReforgeFilters(rf);
    enchantFiltersRef.current = ef;
    setEnchantFilters(ef);
    echostoneFiltersRef.current = ecf;
    setEchostoneFilters(ecf);
    muriasFiltersRef.current = mf;
    setMuriasFilters(mf);

    executeSearch(tags, text, gameItem);
  }, [executeSearch]);

  return {
    // State
    searchText, selectedTags, tagWeights, selectedGameItem, suggestions, showSuggestions, focusIdx, hasFilters,
    attrFilters, reforgeFilters, enchantFilters, echostoneFilters, muriasFilters,
    // Refs
    containerRef, inputRef,
    // Setters (for external init like URL params)
    setSearchText, setSelectedTags, setTagWeights, setSelectedGameItem,
    // Handlers
    handleTextChange, handleSelectTag, handleSelectGameItem, handleSelectItem,
    handleRemoveTag, handleRemoveGameItem,
    handleAddAttrFilter, handleUpdateAttrFilter, handleRemoveAttrFilter,
    handleAddReforgeFilter, handleUpdateReforgeFilter, handleRemoveReforgeFilter,
    handleAddEnchantFilter, handleRemoveEnchantFilter, handleUpdateEnchantEffect,
    handleAddEchostoneFilter, handleUpdateEchostoneFilter, handleRemoveEchostoneFilter,
    handleAddMuriasFilter, handleUpdateMuriasFilter, handleRemoveMuriasFilter,
    handleSubmitSearch, handleClear, handleKeyDown, handleInputFocus,
    // Serialization
    toSearchParams, loadSearchParams,
    // Direct execute
    executeSearch,
  };
}
