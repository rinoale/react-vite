import React, { useState, useCallback } from 'react';
import { Search, X, MoreHorizontal, Package } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { dropdownFull, clearBtnAbsolute } from '../styles/index.js';
import TagBadge from './TagBadge.jsx';

const suggestionBtnBase = 'w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 transition-colors';
const gameItemChip = 'inline-flex items-center gap-1 text-xs leading-none px-2 pt-1 pb-0.5 rounded border bg-orange-900/50 text-orange-300 border-orange-700/50 cursor-default';
const MAX_VISIBLE_TAGS = 3;

const TagSuggestion = ({ item, isFocused, onClick }) => (
  <button
    onClick={onClick}
    className={`${suggestionBtnBase} ${isFocused ? 'bg-gray-700' : 'hover:bg-gray-700/50'}`}
  >
    <TagBadge name={item.label} weight={item.weight} />
  </button>
);

const GameItemSuggestion = ({ item, isFocused, onClick }) => (
  <button
    onClick={onClick}
    className={`${suggestionBtnBase} ${isFocused ? 'bg-gray-700' : 'hover:bg-gray-700/50'}`}
  >
    <Package className="w-3.5 h-3.5 text-orange-400 shrink-0" />
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
    <span className="inline-flex items-center gap-1 ml-auto shrink-0">
      {visible.map((tag, i) => (
        <TagBadge key={i} name={tag.name} weight={tag.weight} />
      ))}
      {hasMore && (
        <button onClick={handleExpand} className="p-0.5 text-gray-500 hover:text-gray-300">
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>
      )}
    </span>
  );
};

const ListingSuggestion = ({ item, isFocused, onClick }) => (
  <button
    onClick={onClick}
    className={`${suggestionBtnBase} ${isFocused ? 'bg-gray-700' : 'hover:bg-gray-700/50'}`}
  >
    <span className="text-gray-300 truncate">{item.label}</span>
    {item.data?.game_item_name && (
      <span className="text-[10px] text-gray-500 shrink-0">{item.data.game_item_name}</span>
    )}
    <ListingTags tags={item.data?.tags} />
  </button>
);

const SUGGESTION_RENDERERS = {
  tag: TagSuggestion,
  game_item: GameItemSuggestion,
  listing: ListingSuggestion,
};

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

  const {
    searchText, selectedTags, tagWeights, selectedGameItem, suggestions, showSuggestions, focusIdx, hasFilters,
    containerRef, inputRef,
    handleTextChange, handleSelectItem, handleRemoveTag, handleRemoveGameItem,
    handleClear, handleKeyDown, handleInputFocus,
  } = search;

  const resolvedPlaceholder = (selectedTags.length > 0 || selectedGameItem)
    ? (addMorePlaceholder || t('marketplace.addMoreTags'))
    : (placeholder || t('marketplace.searchPlaceholder'));

  const onRemoveTag = useCallback((tag) => () => handleRemoveTag(tag), [handleRemoveTag]);
  const onSelectItem = useCallback((item) => () => handleSelectItem(item), [handleSelectItem]);

  return (
    <div ref={containerRef} className={wrapperClassName}>
      <div className={barClassName}>
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
        {selectedGameItem && (
          <span className={gameItemChip}>
            <Package className="w-3 h-3" />
            {selectedGameItem.name}
            <button onClick={handleRemoveGameItem} className="cursor-pointer hover:text-orange-100">
              <X className="w-3 h-3" />
            </button>
          </span>
        )}
        {selectedTags.map((tag) => (
          <TagBadge key={tag} name={tag} weight={tagWeights[tag] || 0} onRemove={onRemoveTag(tag)} />
        ))}
        <input
          ref={inputRef}
          type="text"
          placeholder={resolvedPlaceholder}
          value={searchText}
          onChange={handleTextChange}
          onKeyDown={handleKeyDown}
          onFocus={handleInputFocus}
          className="flex-1 min-w-[80px] bg-transparent text-gray-100 outline-none text-sm"
        />
        {hasFilters && (
          <button onClick={handleClear} className={clearBtnAbsolute}>
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

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
