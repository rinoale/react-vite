import React, { useState, useCallback } from 'react';
import { Search, X, MoreHorizontal, Package, ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  dropdownFull, clearBtnAbsolute, chevronSm,
  filterRow, filterSelect, filterOpBtn,
  filterValueInput, filterRemoveBtn, filterAddSelect, filterBadgeSm,
  searchBarIcon, searchBarInput, suggestionBtn, suggestionIconOrange,
  suggestionTagsWrap, suggestionExpandBtn, suggestionMetaSm,
  gameItemChip, gameItemChipExpanded, chipHeaderRow, chipFilterContent,
} from '../styles/index.js';
import TagBadge from './TagBadge.jsx';

const stopPropagation = (e) => e.stopPropagation();
const MAX_VISIBLE_TAGS = 3;

/* ── Filter category config ── */

const FILTER_CATEGORIES = [
  { key: 'erg_level', i18nKey: 'marketplace.filter.ergLevel', abbr: 'E', group: 'main' },
  { key: 'special_upgrade_level', i18nKey: 'marketplace.filter.specialUpgrade', abbr: 'S', group: 'main' },
  { key: 'reforge_count', i18nKey: 'marketplace.filter.reforgeCount', abbr: 'R', group: 'main' },
  { key: 'damage', i18nKey: 'attrs.damage', abbr: 'Atk', group: 'attrs' },
  { key: 'magic_damage', i18nKey: 'attrs.magic_damage', abbr: 'MA', group: 'attrs' },
  { key: 'balance', i18nKey: 'attrs.balance', abbr: 'Bal', group: 'attrs' },
  { key: 'defense', i18nKey: 'attrs.defense', abbr: 'Def', group: 'attrs' },
  { key: 'protection', i18nKey: 'attrs.protection', abbr: 'Pro', group: 'attrs' },
  { key: 'durability', i18nKey: 'attrs.durability', abbr: 'Dur', group: 'attrs' },
  { key: 'piercing_level', i18nKey: 'attrs.piercing_level', abbr: 'Prc', group: 'attrs' },
];

const MAIN_FILTERS = FILTER_CATEGORIES.filter((c) => c.group === 'main');
const ATTR_FILTERS = FILTER_CATEGORIES.filter((c) => c.group === 'attrs');
const CATEGORY_MAP = Object.fromEntries(FILTER_CATEGORIES.map((c) => [c.key, c]));

const OPS = ['gte', 'lte', 'eq'];
const OP_SYMBOLS = { gte: '\u2265', lte: '\u2264', eq: '=' };

/* ── Sub-components ── */

const FilterRowItem = ({ filter, index, onUpdate, onRemove, t }) => {
  const handleCategory = useCallback((e) => onUpdate(index, { key: e.target.value }), [index, onUpdate]);
  const handleOp = useCallback(() => {
    const next = OPS[(OPS.indexOf(filter.op) + 1) % OPS.length];
    onUpdate(index, { op: next });
  }, [filter.op, index, onUpdate]);
  const handleValue = useCallback((e) => onUpdate(index, { value: e.target.value }), [index, onUpdate]);
  const handleRemove = useCallback(() => onRemove(index), [index, onRemove]);

  return (
    <div className={filterRow}>
      <select value={filter.key} onChange={handleCategory} className={filterSelect}>
        {MAIN_FILTERS.map(({ key, i18nKey }) => (
          <option key={key} value={key}>{t(i18nKey)}</option>
        ))}
        <optgroup label={t('marketplace.filter.attrGroup')}>
          {ATTR_FILTERS.map(({ key, i18nKey }) => (
            <option key={key} value={key}>{t(i18nKey)}</option>
          ))}
        </optgroup>
      </select>
      <button type="button" onClick={handleOp} className={filterOpBtn}>
        <span key={filter.op} className="inline-block animate-op-spin">
          {OP_SYMBOLS[filter.op]}
        </span>
      </button>
      <input
        type="number"
        min="0"
        value={filter.value}
        onChange={handleValue}
        placeholder="0"
        className={filterValueInput}
      />
      <button type="button" onClick={handleRemove} className={filterRemoveBtn}>
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};

const TagSuggestion = ({ item, isFocused, onClick }) => (
  <button
    onClick={onClick}
    className={`${suggestionBtn} ${isFocused ? 'bg-gray-700' : 'hover:bg-gray-700/50'}`}
  >
    <TagBadge name={item.label} weight={item.weight} />
  </button>
);

const GameItemSuggestion = ({ item, isFocused, onClick }) => (
  <button
    onClick={onClick}
    className={`${suggestionBtn} ${isFocused ? 'bg-gray-700' : 'hover:bg-gray-700/50'}`}
  >
    <Package className={suggestionIconOrange} />
    <span className="text-orange-300 truncate">{item.label}</span>
  </button>
);

const ListingTags = ({ tags }) => {
  const [expanded, setExpanded] = useState(false);
  const handleExpand = useCallback((e) => { e.stopPropagation(); setExpanded(true); }, []);
  if (!tags?.length) return null;
  const visible = expanded ? tags : tags.slice(0, MAX_VISIBLE_TAGS);
  const hasMore = tags.length > MAX_VISIBLE_TAGS && !expanded;
  return (
    <span className={suggestionTagsWrap}>
      {visible.map((tag, i) => (
        <TagBadge key={i} name={tag.name} weight={tag.weight} />
      ))}
      {hasMore && (
        <button onClick={handleExpand} className={suggestionExpandBtn}>
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>
      )}
    </span>
  );
};

const ListingSuggestion = ({ item, isFocused, onClick }) => (
  <button
    onClick={onClick}
    className={`${suggestionBtn} ${isFocused ? 'bg-gray-700' : 'hover:bg-gray-700/50'}`}
  >
    <span className="text-gray-300 truncate">{item.label}</span>
    {item.data?.game_item_name && (
      <span className={suggestionMetaSm}>{item.data.game_item_name}</span>
    )}
    <ListingTags tags={item.data?.tags} />
  </button>
);

const SUGGESTION_RENDERERS = {
  tag: TagSuggestion,
  game_item: GameItemSuggestion,
  listing: ListingSuggestion,
};

/* ── Main component ── */

/**
 * Shared search bar with tag chips + game item chip + suggestion dropdown.
 * Must be driven by useListingSearch() hook.
 */
const ListingSearchBar = ({
  search,
  wrapperClassName = 'relative w-full md:w-[28rem]',
  barClassName = 'flex items-center gap-1.5 flex-wrap bg-gray-800 border border-gray-700 rounded-full py-1.5 pl-10 pr-8 min-h-[2.5rem] focus-within:ring-2 focus-within:ring-cyan-500',
  placeholder,
  addMorePlaceholder,
}) => {
  const { t } = useTranslation();
  const [panelOpen, setPanelOpen] = useState(false);

  const {
    searchText, selectedTags, tagWeights, selectedGameItem, suggestions, showSuggestions, focusIdx, hasFilters,
    attrFilters, containerRef, inputRef,
    handleTextChange, handleSelectItem, handleRemoveTag, handleRemoveGameItem,
    handleAddAttrFilter, handleUpdateAttrFilter, handleRemoveAttrFilter,
    handleClear, handleKeyDown, handleInputFocus, executeSearch,
  } = search;

  const isExpanded = panelOpen && !!selectedGameItem;
  const activeFilters = attrFilters.filter((f) => f.value !== '' && f.value != null);

  const resolvedPlaceholder = (selectedTags.length > 0 || selectedGameItem)
    ? (addMorePlaceholder || t('marketplace.addMoreTags'))
    : (placeholder || t('marketplace.searchPlaceholder'));

  const onRemoveTag = useCallback((tag) => () => handleRemoveTag(tag), [handleRemoveTag]);
  const onSelectItem = useCallback((item) => () => handleSelectItem(item), [handleSelectItem]);
  const handleChipClick = useCallback(() => {
    setPanelOpen((prev) => {
      if (prev) executeSearch(selectedTags, searchText, selectedGameItem);
      return !prev;
    });
  }, [executeSearch, selectedTags, searchText, selectedGameItem]);
  const onRemoveGameItemClick = useCallback((e) => { e.stopPropagation(); handleRemoveGameItem(); }, [handleRemoveGameItem]);

  const handleAddFilterSelect = useCallback((e) => {
    const key = e.target.value;
    if (key) handleAddAttrFilter(key);
    e.target.value = '';
  }, [handleAddAttrFilter]);

  return (
    <div ref={containerRef} className={wrapperClassName}>
      <div className={barClassName}>
        {/* search-icon */}
        <Search className={searchBarIcon} />

        {/* game-item-chip — ONE element that expands */}
        {selectedGameItem && (
          <div
            onClick={handleChipClick}
            className={`${gameItemChip} ${isExpanded ? gameItemChipExpanded : ''}`}
          >
            {/* header row — always visible */}
            <div className={chipHeaderRow}>
              <Package className="w-3 h-3" />
              {selectedGameItem.name}
              {/* collapsed filter badges */}
              {!isExpanded && activeFilters.map((f, i) => {
                const cat = CATEGORY_MAP[f.key];
                return (
                  <span key={i} className={filterBadgeSm}>
                    {cat?.abbr}{OP_SYMBOLS[f.op]}{f.value}
                  </span>
                );
              })}
              <ChevronDown className={isExpanded ? `${chevronSm} rotate-180` : chevronSm} />
              <button onClick={onRemoveGameItemClick} className="cursor-pointer hover:text-orange-100">
                <X className="w-3 h-3" />
              </button>
            </div>
            {/* expanding content — same element, revealed by grid animation */}
            <div
              className="grid"
              onClick={stopPropagation}
              style={{
                gridTemplateRows: isExpanded ? '1fr' : '0fr',
                transition: 'grid-template-rows 300ms cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            >
              <div className="overflow-hidden">
                <div className={`${chipFilterContent} ${isExpanded ? 'opacity-100' : 'opacity-0 -translate-y-1'}`}>
                  {attrFilters.map((filter, idx) => (
                    <FilterRowItem
                      key={idx}
                      filter={filter}
                      index={idx}
                      onUpdate={handleUpdateAttrFilter}
                      onRemove={handleRemoveAttrFilter}
                      t={t}
                    />
                  ))}
                  {/* add-filter */}
                  <div className={filterRow}>
                    <select value="" onChange={handleAddFilterSelect} className={filterAddSelect}>
                      <option value="" disabled>
                        + {t('marketplace.filter.addFilter')}
                      </option>
                      {MAIN_FILTERS.map(({ key, i18nKey }) => (
                        <option key={key} value={key}>{t(i18nKey)}</option>
                      ))}
                      <optgroup label={t('marketplace.filter.attrGroup')}>
                        {ATTR_FILTERS.map(({ key, i18nKey }) => (
                          <option key={key} value={key}>{t(i18nKey)}</option>
                        ))}
                      </optgroup>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* tag-chips */}
        {selectedTags.map((tag) => (
          <TagBadge key={tag} name={tag} weight={tagWeights[tag] || 0} onRemove={onRemoveTag(tag)} />
        ))}

        {/* text-input */}
        <input
          ref={inputRef}
          type="text"
          placeholder={resolvedPlaceholder}
          value={searchText}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          onFocus={handleInputFocus}
          className={searchBarInput}
        />

        {/* clear-btn */}
        {hasFilters && (
          <button onClick={handleClear} className={clearBtnAbsolute}>
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* suggestions-dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className={`${dropdownFull} max-h-60 rounded-lg`}>
          {suggestions.map((item, idx) => {
            const Renderer = SUGGESTION_RENDERERS[item.type] || ListingSuggestion;
            return (
              <Renderer
                key={`${item.type}:${item.value}`}
                item={item}
                isFocused={idx === focusIdx}
                onClick={onSelectItem(item)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ListingSearchBar;
