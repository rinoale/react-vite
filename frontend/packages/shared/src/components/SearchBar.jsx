import { useCallback, useRef, useState } from 'react';
import { Search, X as XIcon } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const selectCls = 'text-xs bg-gray-900 border border-gray-600 rounded px-1 py-1 outline-none';
const inputCls = 'text-xs bg-gray-900 border border-gray-600 rounded pl-7 pr-6 py-1 outline-none focus:border-cyan-500';

const SearchBar = ({ defaultQuery = '', defaultBy = 'name', onSearch, placeholder, debounceMs = 300 }) => {
  const { t } = useTranslation();
  const [query, setQuery] = useState(defaultQuery);
  const [by, setBy] = useState(defaultBy);
  const debounceRef = useRef(null);
  const inputRef = useRef(null);

  const handleChange = useCallback((e) => {
    const val = e.target.value;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setQuery(val);
      onSearch({ query: val, by });
    }, debounceMs);
  }, [by, debounceMs, onSearch]);

  const handleByChange = useCallback((e) => {
    const newBy = e.target.value;
    setBy(newBy);
    onSearch({ query, by: newBy });
  }, [query, onSearch]);

  const handleClear = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (inputRef.current) inputRef.current.value = '';
    setQuery('');
    onSearch({ query: '', by });
  }, [by, onSearch]);

  return (
    <div className="flex items-center gap-1">
      <select value={by} onChange={handleByChange} className={selectCls}>
        <option value="name">{t('common.name')}</option>
        <option value="id">ID</option>
      </select>
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-500 w-3 h-3" />
        <input
          ref={inputRef}
          type="text"
          defaultValue={query}
          onChange={handleChange}
          placeholder={placeholder || t('common.searchPlaceholder')}
          className={inputCls}
        />
        {query && (
          <button onClick={handleClear} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
            <XIcon className="w-3 h-3" />
          </button>
        )}
      </div>
    </div>
  );
};

export default SearchBar;
