import { useState, useRef, useEffect, useCallback } from 'react';
import { searchListings, searchTags } from '../api/recommend';
import { searchGameItemsLocal } from '../lib/gameItems';

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

  const debounceRef = useRef(null);
  const containerRef = useRef(null);
  const inputRef = useRef(null);
  const attrFiltersRef = useRef([]);

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
    const validFilters = attrFiltersRef.current.filter((f) => f.key && f.value !== '' && f.value != null);
    try {
      const { data } = await searchListings(
        text?.trim() || '',
        tags.length > 0 ? tags : undefined,
        { gameItemId: gameItem?.id, ...(validFilters.length ? { attrFilters: validFilters } : {}) },
      );
      onResults?.(data, { tags, text: text?.trim() || '', gameItem, attrFilters: validFilters });
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
      const gameItems = searchGameItemsLocal(text.trim(), 3);
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

  // --- Submit search (Enter / button) ---
  const handleSubmitSearch = useCallback(() => {
    setShowSuggestions(false);
    if (onSubmit) {
      onSubmit({ tags: selectedTags, text: searchText, gameItem: selectedGameItem });
    } else {
      executeSearch(selectedTags, searchText, selectedGameItem);
    }
  }, [selectedTags, searchText, selectedGameItem, executeSearch, onSubmit]);

  // --- Attribute filter CRUD ---
  const handleAddAttrFilter = useCallback((key) => {
    const next = [...attrFiltersRef.current, { key, op: 'gte', value: '' }];
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

  const hasFilters = selectedTags.length > 0 || selectedGameItem != null || searchText.trim().length > 0 || attrFilters.some((f) => f.value !== '' && f.value != null);

  return {
    // State
    searchText, selectedTags, tagWeights, selectedGameItem, suggestions, showSuggestions, focusIdx, hasFilters,
    attrFilters,
    // Refs
    containerRef, inputRef,
    // Setters (for external init like URL params)
    setSearchText, setSelectedTags, setTagWeights, setSelectedGameItem,
    // Handlers
    handleTextChange, handleSelectTag, handleSelectGameItem, handleSelectItem,
    handleRemoveTag, handleRemoveGameItem,
    handleAddAttrFilter, handleUpdateAttrFilter, handleRemoveAttrFilter,
    handleSubmitSearch, handleClear, handleKeyDown, handleInputFocus,
    // Direct execute
    executeSearch,
  };
}
