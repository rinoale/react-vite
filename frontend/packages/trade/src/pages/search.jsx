import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { searchGameItems } from '@mabi/shared/api/recommend';

const SearchPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const debounceRef = useRef(null);

  const handleSearch = useCallback((q) => {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await searchGameItems(q.trim());
        setSuggestions(data);
      } catch (error) {
        console.error('Failed to search game items:', error);
      }
    }, 300);
  }, []);

  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current); }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        <h1 className="text-4xl font-black text-center text-white tracking-tight mb-8">
          {t('search.title', 'Item Search')}
        </h1>
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder={t('search.placeholder', 'Search game items...')}
            className="w-full bg-gray-800 border border-gray-700 rounded-xl py-3 pl-12 pr-4 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none text-lg"
          />
        </div>
        {suggestions.length > 0 && (
          <div className="mt-2 bg-gray-800 border border-gray-700 rounded-xl shadow-xl max-h-80 overflow-auto">
            {suggestions.map((gi) => (
              <button
                key={gi.id}
                onClick={() => navigate(`/market?item=${gi.id}&name=${encodeURIComponent(gi.name)}`)}
                className="w-full text-left px-4 py-3 hover:bg-gray-700 text-sm text-gray-200 border-b border-gray-700/50 last:border-b-0 transition-colors"
              >
                {gi.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SearchPage;
