import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search, ShoppingBag, Wand2, Hammer, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getListings, getListingDetail, getListingsByGameItem, searchGameItems } from '@mabi/shared/api/recommend';

const SLOT_LABELS = { 0: 'Prefix', 1: 'Suffix' };

const Marketplace = () => {
  const { t } = useTranslation();
  const [listings, setListings] = useState([]);
  const [selectedListing, setSelectedListing] = useState(null);
  const [listingDetail, setListingDetail] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Game item filter state
  const [gameItemQuery, setGameItemQuery] = useState('');
  const [gameItemSuggestions, setGameItemSuggestions] = useState([]);
  const [selectedGameItem, setSelectedGameItem] = useState(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceRef = useRef(null);
  const suggestionsRef = useRef(null);

  const fetchListings = async () => {
    try {
      const { data } = await getListings();
      setListings(data);
    } catch (error) {
      console.error("Failed to fetch listings:", error);
    }
  };

  const fetchDetail = async (listingId) => {
    try {
      const { data } = await getListingDetail(listingId);
      setListingDetail(data);
    } catch (error) {
      console.error("Failed to fetch listing detail:", error);
      setListingDetail(null);
    }
  };

  const [searchParams] = useSearchParams();

  useEffect(() => {
    const itemId = searchParams.get('item');
    const itemName = searchParams.get('name');
    if (itemId) {
      const gi = { id: Number(itemId), name: itemName || '' };
      setSelectedGameItem(gi);
      setGameItemQuery(gi.name);
      getListingsByGameItem(gi.id)
        .then(({ data }) => setListings(data))
        .catch(() => fetchListings());
    } else {
      fetchListings();
    }
  }, []);

  useEffect(() => {
    if (selectedListing) {
      fetchDetail(selectedListing.id);
    } else {
      setListingDetail(null);
    }
  }, [selectedListing]);

  // Close suggestions on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleGameItemSearch = useCallback((q) => {
    setGameItemQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setGameItemSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await searchGameItems(q.trim());
        setGameItemSuggestions(data);
        setShowSuggestions(true);
      } catch (error) {
        console.error("Failed to search game items:", error);
      }
    }, 300);
  }, []);

  const handleSelectGameItem = async (gi) => {
    setSelectedGameItem(gi);
    setGameItemQuery(gi.name);
    setShowSuggestions(false);
    setSelectedListing(null);
    try {
      const { data } = await getListingsByGameItem(gi.id);
      setListings(data);
    } catch (error) {
      console.error("Failed to fetch listings by game item:", error);
    }
  };

  const clearGameItemFilter = async () => {
    setSelectedGameItem(null);
    setGameItemQuery('');
    setGameItemSuggestions([]);
    setSelectedListing(null);
    fetchListings();
  };

  const filteredListings = listings.filter(listing =>
    listing.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
          <h1 className="text-3xl font-bold text-cyan-400 flex items-center gap-2">
            <ShoppingBag className="w-8 h-8" />
            {t('marketplace.title')}
          </h1>

          <div className="flex gap-3 w-full md:w-auto">
            {/* Game item filter */}
            <div className="relative w-full md:w-64" ref={suggestionsRef}>
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder={t('marketplace.gameItemFilter')}
                value={gameItemQuery}
                onChange={(e) => handleGameItemSearch(e.target.value)}
                onFocus={() => { if (gameItemSuggestions.length > 0) setShowSuggestions(true); }}
                className="w-full bg-gray-800 border border-gray-700 rounded-full py-2 pl-9 pr-8 text-sm text-gray-100 focus:ring-2 focus:ring-orange-500 outline-none"
              />
              {selectedGameItem && (
                <button
                  onClick={clearGameItemFilter}
                  className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
              {showSuggestions && gameItemSuggestions.length > 0 && (
                <div className="absolute z-10 mt-1 w-full bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-60 overflow-auto">
                  {gameItemSuggestions.map((gi) => (
                    <button
                      key={gi.id}
                      onClick={() => handleSelectGameItem(gi)}
                      className="w-full text-left px-4 py-2 text-sm hover:bg-gray-700 transition-colors"
                    >
                      {gi.name}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Text search */}
            <div className="relative w-full md:w-72">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder={t('marketplace.searchPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-full py-2 pl-10 pr-4 text-gray-100 focus:ring-2 focus:ring-cyan-500 outline-none"
              />
            </div>
          </div>
        </div>

        {selectedGameItem && (
          <div className="mb-4 flex items-center gap-2">
            <span className="text-xs font-bold text-orange-400 uppercase">{t('marketplace.filteredBy')}</span>
            <span className="text-sm bg-orange-900/40 text-orange-300 px-3 py-1 rounded-full border border-orange-700/50">
              {selectedGameItem.name}
            </span>
            <button onClick={clearGameItemFilter} className="text-xs text-gray-500 hover:text-white underline">
              {t('marketplace.clearFilter')}
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Listing Grid */}
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredListings.length > 0 ? (
              filteredListings.map(listing => (
                <div
                  key={listing.id}
                  onClick={() => setSelectedListing(listing)}
                  className={`bg-gray-800 p-4 rounded-xl border cursor-pointer transition-all hover:scale-[1.02] ${selectedListing?.id === listing.id ? 'border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.3)]' : 'border-gray-700 hover:border-gray-600'}`}
                >
                  <h3 className="font-bold text-lg mb-1">{listing.name}</h3>
                  {(listing.item_type || listing.item_grade) && (
                    <p className="text-xs text-gray-400 mb-2">
                      {[listing.item_type, listing.item_grade].filter(Boolean).join(' / ')}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2 mb-3">
                    {listing.prefix_enchant_name && (
                      <span className="text-xs px-2 py-1 bg-purple-900/50 text-purple-300 rounded-full flex items-center gap-1">
                        <Wand2 className="w-3 h-3" />
                        {listing.prefix_enchant_name}
                      </span>
                    )}
                    {listing.suffix_enchant_name && (
                      <span className="text-xs px-2 py-1 bg-purple-900/50 text-purple-300 rounded-full flex items-center gap-1">
                        <Wand2 className="w-3 h-3" />
                        {listing.suffix_enchant_name}
                      </span>
                    )}
                    {listing.reforge_count > 0 && (
                      <span className="text-xs px-2 py-1 bg-cyan-900/50 text-cyan-300 rounded-full flex items-center gap-1">
                        <Hammer className="w-3 h-3" />
                        {t('marketplace.reforges', { count: listing.reforge_count })}
                      </span>
                    )}
                    {listing.erg_grade && (
                      <span className="text-xs px-2 py-1 bg-yellow-900/50 text-yellow-300 rounded-full">
                        ERG {listing.erg_grade}{listing.erg_level != null ? ` Lv.${listing.erg_level}` : ''}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">{formatDate(listing.created_at)}</p>
                </div>
              ))
            ) : (
              <div className="md:col-span-2 bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-12 text-center text-gray-500 flex flex-col items-center">
                <ShoppingBag className="w-12 h-12 mb-4 opacity-50" />
                <p>{listings.length === 0 ? t('marketplace.noListings') : t('marketplace.noResults')}</p>
              </div>
            )}
          </div>

          {/* Sidebar: Listing Detail */}
          <div className="lg:col-span-1 space-y-6">
            {selectedListing && listingDetail ? (
              <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 sticky top-6">
                <h2 className="text-2xl font-bold mb-2">{listingDetail.name}</h2>
                {(listingDetail.item_type || listingDetail.item_grade) && (
                  <p className="text-sm text-gray-400 mb-4">
                    {[listingDetail.item_type, listingDetail.item_grade].filter(Boolean).join(' / ')}
                  </p>
                )}

                {listingDetail.erg_grade && (
                  <div className="mb-4">
                    <span className="text-xs px-2 py-1 bg-yellow-900/50 text-yellow-300 rounded-full">
                      ERG {listingDetail.erg_grade}{listingDetail.erg_level != null ? ` Lv.${listingDetail.erg_level}` : ''}
                    </span>
                  </div>
                )}

                {/* Enchants */}
                {(listingDetail.prefix_enchant || listingDetail.suffix_enchant) && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-purple-400 mb-2 flex items-center gap-1">
                      <Wand2 className="w-4 h-4" />
                      {t('marketplace.enchantLabel')}
                    </h3>
                    <div className="space-y-2">
                      {[listingDetail.prefix_enchant, listingDetail.suffix_enchant].filter(Boolean).map((enc, idx) => (
                        <div key={idx} className="bg-gray-900/50 p-3 rounded border border-gray-700">
                          <div className="flex justify-between items-center mb-1">
                            <span className="text-sm font-medium text-purple-300">{enc.enchant_name}</span>
                            <span className="text-xs text-gray-400">{SLOT_LABELS[enc.slot] || enc.slot}</span>
                          </div>
                          {enc.effects?.length > 0 && (
                            <ul className="space-y-0.5">
                              {enc.effects.map((eff, i) => (
                                <li key={i} className="text-xs text-gray-400">
                                  {eff.raw_text}
                                  {eff.value != null ? (
                                    <span className="text-cyan-300 ml-1">({eff.value})</span>
                                  ) : eff.min_value != null && (
                                    <span className="text-gray-500 ml-1">({eff.min_value === eff.max_value ? eff.min_value : `${eff.min_value}~${eff.max_value}`})</span>
                                  )}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Reforge */}
                {listingDetail.reforge_options?.length > 0 && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-cyan-400 mb-2 flex items-center gap-1">
                      <Hammer className="w-4 h-4" />
                      {t('marketplace.reforgeLabel')}
                    </h3>
                    <div className="space-y-2">
                      {listingDetail.reforge_options.map((opt, idx) => (
                        <div key={idx} className="bg-gray-900/50 p-3 rounded border border-gray-700 flex justify-between items-center">
                          <span className="text-sm text-cyan-300">{opt.option_name}</span>
                          {opt.level != null && (
                            <span className="text-xs bg-cyan-900/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-700/50">
                              Lv.{opt.level} / {opt.max_level}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-8 text-center text-gray-500 flex flex-col items-center">
                <ShoppingBag className="w-12 h-12 mb-4 opacity-50" />
                <p>{t('marketplace.selectListing')}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Marketplace;
