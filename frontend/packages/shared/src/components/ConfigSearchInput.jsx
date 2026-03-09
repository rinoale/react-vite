import React, { useState, useRef, useEffect } from 'react';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { dropdownFull } from '../styles';

/**
 * Search-and-select dropdown for correcting OCR values from config data.
 *
 * @param {Array} items - Config items to search through
 * @param {Function} getLabel - (item) => display string
 * @param {Function} onSelect - Called with the selected item
 * @param {Function} onCancel - Called when user cancels (Escape / click outside)
 * @param {string} placeholder - Input placeholder text
 */
const ConfigSearchInput = ({ items, getLabel, onSelect, onCancel, placeholder, showAllOnEmpty = false }) => {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [highlightIdx, setHighlightIdx] = useState(0);
  const inputRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  // Click outside to cancel
  useEffect(() => {
    const handler = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        onCancel();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onCancel]);

  const filtered = query.length > 0
    ? items.filter(item => getLabel(item).toLowerCase().includes(query.toLowerCase())).slice(0, 30)
    : showAllOnEmpty ? items.slice(0, 30) : [];

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onCancel();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered.length > 0) {
      e.preventDefault();
      onSelect(filtered[highlightIdx]);
    }
  };

  return (
    <div ref={containerRef} className="relative flex-1">
      <div className="flex items-center gap-1">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setHighlightIdx(0); }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="flex-1 bg-gray-900 border border-orange-500 rounded px-2 py-1 text-sm text-gray-200 focus:ring-1 focus:ring-orange-500 outline-none"
        />
        <button onClick={onCancel} className="p-0.5 text-gray-500 hover:text-gray-300" title={t('sections.cancel')}>
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      {filtered.length > 0 && (
        <div className={dropdownFull}>
          {filtered.map((item, i) => (
            <div
              key={i}
              onClick={() => onSelect(item)}
              className={`px-3 py-1.5 text-sm cursor-pointer border-b border-gray-700/50 last:border-0 ${
                i === highlightIdx
                  ? 'bg-orange-600/30 text-orange-300'
                  : 'text-gray-300 hover:bg-orange-600/20 hover:text-orange-300'
              }`}
            >
              {getLabel(item)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ConfigSearchInput;
