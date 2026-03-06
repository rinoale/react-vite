import React, { useState, useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { ShoppingBag, Wand2, Hammer } from 'lucide-react';
import { badgeCyan, badgeYellow, badgePink, cardSlot } from '@mabi/shared/styles';
import { useTranslation } from 'react-i18next';
import { getListings, getListingDetail, searchListings } from '@mabi/shared/api/recommend';
import { useListingSearch } from '@mabi/shared/hooks/useListingSearch';
import ListingSearchBar from '@mabi/shared/components/ListingSearchBar';
import TagBadge from '@mabi/shared/components/TagBadge';

const SLOT_LABELS = { 0: 'Prefix', 1: 'Suffix' };

const ATTR_LABELS = {
  damage: '공격력', magic_damage: '마법공격력', additional_damage: '추가대미지',
  balance: '밸런스', defense: '방어', protection: '보호',
  magic_defense: '마법방어', magic_protection: '마법보호',
  durability: '내구력', piercing_level: '관통 레벨',
};

const Marketplace = () => {
  const { t } = useTranslation();
  const [listings, setListings] = useState([]);
  const [selectedListing, setSelectedListing] = useState(null);
  const [listingDetail, setListingDetail] = useState(null);

  // --- Fetch helpers ---
  const fetchListings = useCallback(async () => {
    try {
      const { data } = await getListings();
      setListings(data);
    } catch (error) {
      console.error("Failed to fetch listings:", error);
    }
  }, []);

  const fetchDetail = useCallback(async (listingId) => {
    try {
      const { data } = await getListingDetail(listingId);
      setListingDetail(data);
    } catch (error) {
      console.error("Failed to fetch listing detail:", error);
      setListingDetail(null);
    }
  }, []);

  const handleSearchResults = useCallback((data) => {
    setListings(data);
  }, []);

  const handleSearchClear = useCallback(() => {
    setSelectedListing(null);
    fetchListings();
  }, [fetchListings]);

  const handleSelectListing = useCallback((listing) => {
    setSelectedListing(listing);
  }, []);

  const search = useListingSearch({
    onResults: handleSearchResults,
    onSelectListing: handleSelectListing,
    onClear: handleSearchClear,
  });

  // --- Init from router state ---
  const location = useLocation();

  useEffect(() => {
    const st = location.state || {};
    const name = st.text || '';
    const tags = st.tags || [];
    const targetId = st.listingId || null;

    const init = async () => {
      if (name) search.setSearchText(name);
      if (tags.length) {
        search.setSelectedTags(tags);
        if (st.tagWeights) search.setTagWeights(st.tagWeights);
      }

      let data;
      if (name || tags.length) {
        try {
          const res = await searchListings(name, tags.length ? tags : undefined);
          data = res.data;
        } catch {
          const res = await getListings();
          data = res.data;
        }
      } else {
        const res = await getListings();
        data = res.data;
      }
      setListings(data);

      if (targetId) {
        const match = data.find((l) => l.id === targetId);
        if (match) {
          setSelectedListing(match);
        } else {
          setSelectedListing({ id: targetId, name: '' });
        }
      }
    };
    init();
  }, []);

  useEffect(() => {
    if (selectedListing) {
      fetchDetail(selectedListing.id);
    } else {
      setListingDetail(null);
    }
  }, [selectedListing, fetchDetail]);

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

          <ListingSearchBar search={search} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Listing Grid */}
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
            {listings.length > 0 ? (
              listings.map(listing => (
                <div
                  key={listing.id}
                  onClick={() => handleSelectListing(listing)}
                  className={`bg-gray-800 p-4 rounded-xl border cursor-pointer transition-all hover:scale-[1.02] ${selectedListing?.id === listing.id ? 'border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.3)]' : 'border-gray-700 hover:border-gray-600'}`}
                >
                  <h3 className="font-bold text-lg mb-1">{listing.name}</h3>
                  {listing.game_item_name && (
                    <p className="text-xs text-gray-400 mb-1">{listing.game_item_name}</p>
                  )}
                  {listing.tags?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {listing.tags.map((tag, idx) => (
                        <TagBadge key={idx} name={tag.name} weight={tag.weight} />
                      ))}
                    </div>
                  )}
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
                <h2 className="text-2xl font-bold mb-1">{listingDetail.name}</h2>
                {listingDetail.game_item_name && (
                  <p className="text-sm text-gray-400 mb-2">{listingDetail.game_item_name}</p>
                )}
                {listingDetail.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-4">
                    {listingDetail.tags.map((tag, idx) => (
                      <TagBadge key={idx} name={tag.name} weight={tag.weight} />
                    ))}
                  </div>
                )}

                {/* Item Attrs */}
                {(() => {
                  const attrs = Object.entries(ATTR_LABELS).filter(([k]) => listingDetail[k] != null);
                  if (!attrs.length) return null;
                  return (
                    <div className="mb-4">
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                        {attrs.map(([k, label]) => (
                          <div key={k} className="flex justify-between text-xs">
                            <span className="text-gray-500">{label}</span>
                            <span className="text-gray-200">{listingDetail[k]}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}

                {/* Enchants */}
                {(listingDetail.prefix_enchant || listingDetail.suffix_enchant) && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-purple-400 mb-2 flex items-center gap-1">
                      <Wand2 className="w-4 h-4" />
                      {t('marketplace.enchantLabel')}
                    </h3>
                    <div className="space-y-2">
                      {[listingDetail.prefix_enchant, listingDetail.suffix_enchant].filter(Boolean).map((enc, idx) => (
                        <div key={idx} className={cardSlot}>
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
                        <div key={idx} className={`${cardSlot} flex justify-between items-center`}>
                          <span className="text-sm text-cyan-300">{opt.option_name}</span>
                          {opt.level != null && (
                            <span className={badgeCyan}>
                              Lv.{opt.level} / {opt.max_level}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Special Upgrade */}
                {listingDetail.special_upgrade_type && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-pink-400 mb-2">{t('marketplace.specialUpgradeLabel')}</h3>
                    <div className={`${cardSlot} flex justify-between items-center`}>
                      <span className="text-sm text-pink-300">
                        {t(`marketplace.specialUpgrade${listingDetail.special_upgrade_type}`)}
                      </span>
                      {listingDetail.special_upgrade_level != null && (
                        <span className={badgePink}>
                          {t('marketplace.specialUpgradeLevel', { level: listingDetail.special_upgrade_level })}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Erg */}
                {listingDetail.erg_grade && (
                  <div className="mb-4">
                    <h3 className="text-sm font-semibold text-yellow-400 mb-2">{t('marketplace.ergLabel')}</h3>
                    <div className={`${cardSlot} flex justify-between items-center`}>
                      <span className="text-sm text-yellow-300">{t('marketplace.ergGrade', { grade: listingDetail.erg_grade })}</span>
                      {listingDetail.erg_level != null && (
                        <span className={badgeYellow}>
                          Lv.{listingDetail.erg_level}
                        </span>
                      )}
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
