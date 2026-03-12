import React, { useState, useCallback } from 'react';
import { Search, X, MoreHorizontal, Package, ChevronDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  dropdownFull, clearBtnAbsolute, chevronSm,
  filterBadgeSm,
  searchBarIcon, searchBarInput, suggestionBtn, suggestionIconOrange,
  suggestionTagsWrap, suggestionExpandBtn, suggestionMetaSm,
  gameItemChip, gameItemChipExpanded, chipHeaderRow,
} from '../styles/index.js';
import TagBadge from './TagBadge.jsx';
import ChipFilterPanel from './ChipFilterPanel.jsx';
import { FILTER_MAP, OP_SYMBOLS } from '../lib/filterConstants.js';

const stopPropagation = (e) => e.stopPropagation();
const MAX_VISIBLE_TAGS = 3;

/* ── Suggestion sub-components ── */

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
        <span role="button" tabIndex={0} onClick={handleExpand} onKeyDown={(e) => e.key === 'Enter' && handleExpand(e)} className={suggestionExpandBtn}>
          <MoreHorizontal className="w-3.5 h-3.5" />
        </span>
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

/* ── Collapsed badge helpers ── */

const enchantBadgeSm = 'text-[10px] font-mono leading-none px-1 py-0.5 rounded bg-purple-800/50 text-purple-300';
const echostoneBadgeSm = 'text-[10px] font-mono leading-none px-1 py-0.5 rounded bg-cyan-800/50 text-cyan-300';
const muriasBadgeSm = 'text-[10px] font-mono leading-none px-1 py-0.5 rounded bg-green-800/50 text-green-300';

/* ── Main component ── */

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
    attrFilters, reforgeFilters, enchantFilters, echostoneFilters, muriasFilters, containerRef, inputRef,
    handleTextChange, handleSelectItem, handleRemoveTag, handleRemoveGameItem,
    handleAddAttrFilter, handleUpdateAttrFilter, handleRemoveAttrFilter,
    handleAddReforgeFilter, handleUpdateReforgeFilter, handleRemoveReforgeFilter,
    handleAddEnchantFilter, handleRemoveEnchantFilter, handleUpdateEnchantEffect,
    handleAddEchostoneFilter, handleUpdateEchostoneFilter, handleRemoveEchostoneFilter,
    handleAddMuriasFilter, handleUpdateMuriasFilter, handleRemoveMuriasFilter,
    handleClear, handleKeyDown, handleInputFocus, executeSearch,
  } = search;

  const isExpanded = panelOpen && !!selectedGameItem;
  const activeAttrFilters = attrFilters.filter((f) => (f.value !== '' && f.value != null) || f.grade || f.type);
  const activeReforgeFilters = reforgeFilters;

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

  return (
    <div ref={containerRef} className={wrapperClassName}>
      <div className={barClassName}>
        {/* search-icon */}
        <Search className={searchBarIcon} />

        {/* game-item-chip */}
        {selectedGameItem && (
          <div
            onClick={handleChipClick}
            className={`${gameItemChip} ${isExpanded ? gameItemChipExpanded : ''}`}
          >
            {/* header row */}
            <div className={chipHeaderRow}>
              <Package className="w-3 h-3" />
              {selectedGameItem.name}
              {/* collapsed attr badges */}
              {!isExpanded && activeAttrFilters.map((f, i) => {
                const opt = FILTER_MAP[f.key];
                let label = '';
                if (opt?.kind === 'erg') {
                  label = f.grade || '';
                  if (f.value) label += `${OP_SYMBOLS[f.op]}${f.value}`;
                } else if (opt?.kind === 'special_upgrade') {
                  label = f.type ? t(`marketplace.filter.specialUpgradeType.${f.type}`) : '';
                  if (f.value) label += `${OP_SYMBOLS[f.op]}${f.value}`;
                } else {
                  label = opt?.abbr || '';
                  if (f.value) label += `${OP_SYMBOLS[f.op]}${f.value}`;
                }
                return <span key={`a${i}`} className={filterBadgeSm}>{label}</span>;
              })}
              {/* collapsed reforge badges */}
              {!isExpanded && activeReforgeFilters.map((f, i) => (
                <span key={`r${i}`} className={filterBadgeSm}>
                  {f.option_name.slice(0, 4)}{f.level ? `${OP_SYMBOLS[f.op]}${f.level}` : ''}
                </span>
              ))}
              {/* collapsed enchant badges */}
              {!isExpanded && enchantFilters.map((f, i) => (
                <span key={`e${i}`} className={enchantBadgeSm}>
                  {f.name}
                </span>
              ))}
              {/* collapsed echostone badges */}
              {!isExpanded && echostoneFilters.map((f, i) => (
                <span key={`es${i}`} className={echostoneBadgeSm}>
                  {f.option_name.slice(0, 6)}{f.level ? `${OP_SYMBOLS[f.op]}${f.level}` : ''}
                </span>
              ))}
              {/* collapsed murias badges */}
              {!isExpanded && muriasFilters.map((f, i) => (
                <span key={`m${i}`} className={muriasBadgeSm}>
                  {f.option_name.slice(0, 6)}{f.level ? `${OP_SYMBOLS[f.op]}${f.level}` : ''}
                </span>
              ))}
              <ChevronDown className={isExpanded ? `${chevronSm} rotate-180` : chevronSm} />
              <button onClick={onRemoveGameItemClick} className="cursor-pointer hover:text-orange-100">
                <X className="w-3 h-3" />
              </button>
            </div>
            {/* expanding content */}
            <div
              className="grid"
              onClick={stopPropagation}
              style={{
                gridTemplateRows: isExpanded ? '1fr' : '0fr',
                transition: 'grid-template-rows 300ms cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            >
              <div className={isExpanded ? 'overflow-visible' : 'overflow-hidden'}>
                <ChipFilterPanel
                  isExpanded={isExpanded}
                  itemName={selectedGameItem?.name}
                  itemType={selectedGameItem?.type}
                  attrFilters={attrFilters}
                  onAddAttrFilter={handleAddAttrFilter}
                  onUpdateAttrFilter={handleUpdateAttrFilter}
                  onRemoveAttrFilter={handleRemoveAttrFilter}
                  reforgeFilters={reforgeFilters}
                  onAddReforgeFilter={handleAddReforgeFilter}
                  onUpdateReforgeFilter={handleUpdateReforgeFilter}
                  onRemoveReforgeFilter={handleRemoveReforgeFilter}
                  enchantFilters={enchantFilters}
                  onAddEnchantFilter={handleAddEnchantFilter}
                  onRemoveEnchantFilter={handleRemoveEnchantFilter}
                  onUpdateEnchantEffect={handleUpdateEnchantEffect}
                  echostoneFilters={echostoneFilters}
                  onAddEchostoneFilter={handleAddEchostoneFilter}
                  onUpdateEchostoneFilter={handleUpdateEchostoneFilter}
                  onRemoveEchostoneFilter={handleRemoveEchostoneFilter}
                  muriasFilters={muriasFilters}
                  onAddMuriasFilter={handleAddMuriasFilter}
                  onUpdateMuriasFilter={handleUpdateMuriasFilter}
                  onRemoveMuriasFilter={handleRemoveMuriasFilter}
                />
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
