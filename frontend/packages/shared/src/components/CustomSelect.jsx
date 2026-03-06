import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import {
  dropdownFull, dropdownInline, dropdownOption, dropdownOptionCompact,
  dropdownTrigger, dropdownTriggerInline,
} from '@mabi/shared/styles';

const CustomSelect = ({
  value,
  onChange,
  options,
  placeholder = '—',
  variant = 'form',
  searchable = false,
  searchValue,
  onSearchChange,
  className = '',
  triggerClassName = '',
  optionClassName = '',
  dropdownClassName = '',
  renderOption,
  renderSelected,
}) => {
  const [open, setOpen] = useState(false);
  const [focusIdx, setFocusIdx] = useState(-1);
  const containerRef = useRef(null);
  const listRef = useRef(null);
  const inputRef = useRef(null);

  const selected = options.find((o) => o.value === value) || null;

  // --- Close on outside click ---
  useEffect(() => {
    if (!open) return;
    const handleClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  // --- Scroll focused option into view ---
  useEffect(() => {
    if (!open || focusIdx < 0 || !listRef.current) return;
    const item = listRef.current.children[focusIdx];
    if (item) item.scrollIntoView({ block: 'nearest' });
  }, [focusIdx, open]);

  // --- Open dropdown when searchable has options ---
  useEffect(() => {
    if (searchable && options.length > 0 && searchValue?.trim()) {
      setOpen(true);
      setFocusIdx(0);
    } else if (searchable && options.length === 0) {
      setOpen(false);
    }
  }, [searchable, options, searchValue]);

  const handleToggle = useCallback(() => {
    if (searchable) return;
    setOpen((prev) => {
      if (!prev) {
        const idx = options.findIndex((o) => o.value === value);
        setFocusIdx(idx >= 0 ? idx : 0);
      }
      return !prev;
    });
  }, [searchable, options, value]);

  const handleSelect = useCallback(
    (optValue) => {
      onChange(optValue);
      setOpen(false);
    },
    [onChange],
  );

  const handleKeyDown = useCallback(
    (e) => {
      if (!open) {
        if (!searchable && (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown')) {
          e.preventDefault();
          handleToggle();
        }
        return;
      }

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setFocusIdx((prev) => Math.min(prev + 1, options.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setFocusIdx((prev) => Math.max(prev - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (focusIdx >= 0 && focusIdx < options.length) {
            handleSelect(options[focusIdx].value);
          }
          break;
        case 'Escape':
          e.preventDefault();
          setOpen(false);
          break;
        case 'Tab':
          setOpen(false);
          break;
        default:
          break;
      }
    },
    [open, searchable, focusIdx, options, handleToggle, handleSelect],
  );

  const handleOptionMouseEnter = useCallback((idx) => {
    setFocusIdx(idx);
  }, []);

  const handleOptionClick = useCallback(
    (optValue) => {
      handleSelect(optValue);
    },
    [handleSelect],
  );

  const handleInputChange = useCallback(
    (e) => {
      if (onSearchChange) onSearchChange(e.target.value);
    },
    [onSearchChange],
  );

  // --- Variant styles ---
  const isInline = variant === 'inline';

  const triggerBase = isInline ? dropdownTriggerInline : dropdownTrigger;
  const dropdownCls = isInline ? dropdownInline : dropdownFull;
  const optionBase = isInline ? dropdownOptionCompact : dropdownOption;

  // --- Render ---
  const renderLabel = () => {
    if (selected) {
      if (renderSelected) return renderSelected(selected);
      return <span className={selected.className || ''}>{selected.label}</span>;
    }
    return <span className="text-gray-500">{placeholder}</span>;
  };

  const renderOpt = (opt, idx) => {
    const isFocused = idx === focusIdx;
    const isSelected = opt.value === value;
    const focusCls = isFocused ? 'bg-gray-700' : '';
    const selectedCls = isSelected ? 'text-white font-semibold' : 'text-gray-300';

    return (
      <div
        key={opt.value}
        role="option"
        aria-selected={isSelected}
        className={`${optionBase} ${focusCls} ${selectedCls} ${opt.className || ''} ${optionClassName}`}
        onMouseEnter={() => handleOptionMouseEnter(idx)}
        onClick={() => handleOptionClick(opt.value)}
      >
        {renderOption ? renderOption(opt, { isFocused, isSelected }) : opt.label}
      </div>
    );
  };

  // --- Searchable mode ---
  if (searchable) {
    return (
      <div ref={containerRef} className={`relative ${className}`}>
        <input
          ref={inputRef}
          type="text"
          autoFocus
          value={searchValue || ''}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={triggerClassName}
        />
        {open && options.length > 0 && (
          <div ref={listRef} role="listbox" className={`${dropdownCls} ${dropdownClassName}`}>
            {options.map(renderOpt)}
          </div>
        )}
      </div>
    );
  }

  // --- Static mode ---
  return (
    <div ref={containerRef} className={`relative ${isInline ? 'inline-block' : ''} ${className}`}>
      <div
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        tabIndex={0}
        className={`${triggerBase} ${triggerClassName}`}
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
      >
        {renderLabel()}
        {!isInline && (
          <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
        )}
      </div>

      {open && (
        <div ref={listRef} role="listbox" className={`${dropdownCls} ${dropdownClassName}`}>
          {options.map(renderOpt)}
        </div>
      )}
    </div>
  );
};

export default CustomSelect;
