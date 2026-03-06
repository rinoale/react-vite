import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Hash, Wand2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { searchListings } from '@mabi/shared/api/recommend';
import { getTagColor } from '@mabi/shared/lib/tagColors';
import CustomSelect from '@mabi/shared/components/CustomSelect';

const SearchResultOption = ({ opt }) => {
  const listing = opt.data;
  return (
    <div>
      <div className="text-sm text-gray-200 font-medium">{listing.name}</div>
      <div className="flex flex-wrap gap-1.5 mt-1">
        {listing.prefix_enchant_name && (
          <span className="text-[10px] px-1.5 py-0.5 bg-purple-900/50 text-purple-300 rounded-full inline-flex items-center gap-0.5">
            <Wand2 className="w-2.5 h-2.5" />{listing.prefix_enchant_name}
          </span>
        )}
        {listing.suffix_enchant_name && (
          <span className="text-[10px] px-1.5 py-0.5 bg-purple-900/50 text-purple-300 rounded-full inline-flex items-center gap-0.5">
            <Wand2 className="w-2.5 h-2.5" />{listing.suffix_enchant_name}
          </span>
        )}
        {listing.tags?.map((tag, idx) => {
          const c = getTagColor(tag.weight);
          return (
            <span key={idx} className={`text-[10px] px-1.5 py-0.5 rounded-full inline-flex items-center gap-0.5 ${c.bg} ${c.text}`}>
              <Hash className={`w-2.5 h-2.5 ${c.icon}`} />{tag.name}
            </span>
          );
        })}
      </div>
    </div>
  );
};

const renderSearchOption = (opt) => <SearchResultOption opt={opt} />;

const SearchPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState([]);
  const debounceRef = useRef(null);

  const handleSearchChange = useCallback((q) => {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setOptions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await searchListings(q.trim());
        setOptions(data.map((listing) => ({
          value: listing.id,
          label: listing.name,
          data: listing,
        })));
      } catch (error) {
        console.error('Failed to search:', error);
      }
    }, 300);
  }, []);

  const handleSelect = useCallback((listingId) => {
    navigate(`/market?id=${listingId}`);
  }, [navigate]);

  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current); }, []);

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex items-center justify-center p-6">
      <div className="w-full max-w-lg">
        <h1 className="text-4xl font-black text-center text-white tracking-tight mb-8">
          {t('search.title', 'Item Search')}
        </h1>
        <div className="relative">
          <Search className="absolute left-4 top-3.5 text-gray-400 w-5 h-5 z-10 pointer-events-none" />
          <CustomSelect
            searchable
            searchValue={query}
            onSearchChange={handleSearchChange}
            options={options}
            onChange={handleSelect}
            placeholder={t('search.placeholder', 'Search items, tags...')}
            triggerClassName="w-full bg-gray-800 border border-gray-700 rounded-xl py-3 pl-12 pr-4 text-gray-100 focus:ring-2 focus:ring-cyan-500 focus:border-transparent outline-none text-lg"
            dropdownClassName="rounded-xl shadow-xl max-h-[28rem] border-gray-700"
            optionClassName="px-4 py-3 border-b border-gray-700/50 last:border-b-0"
          renderOption={renderSearchOption}
          />
        </div>
      </div>
    </div>
  );
};

export default SearchPage;
