import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, ChevronDown, ChevronRight, Package, RefreshCw } from 'lucide-react';
import { getListings, getListingDetail } from '@mabi/shared/api/admin';
import TagBadge from '@mabi/shared/components/TagBadge';
import LevelBadge from '@mabi/shared/components/LevelBadge';

const ATTR_LABELS = {
  damage: '공격력', magic_damage: '마법공격력', additional_damage: '추가대미지',
  balance: '밸런스', defense: '방어', protection: '보호',
  magic_defense: '마법방어', magic_protection: '마법보호',
  durability: '내구력', piercing_level: '관통 레벨',
};

const toRankLabel = (rank) => {
  const n = Number(rank);
  if (!Number.isFinite(n)) return String(rank ?? '');
  if (n >= 10 && n <= 15) return String.fromCharCode('A'.charCodeAt(0) + (n - 10));
  return String(n);
};

const ListingsPanel = () => {
  const { t } = useTranslation();
  const [listings, setListings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });
  const [expandedListingIds, setExpandedListingIds] = useState({});
  const [detailByListing, setDetailByListing] = useState({});
  const [loadingDetail, setLoadingDetail] = useState({});

  const fetchListings = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await getListings({ limit: pagination.limit, offset: pagination.offset });
      setListings(data.rows || []);
    } catch (error) {
      console.error('Error fetching listings:', error);
      setListings([]);
    } finally {
      setIsLoading(false);
    }
  }, [pagination.offset, pagination.limit]);

  useEffect(() => {
    fetchListings();
  }, [fetchListings]);

  const fetchListingDetail = async (listingId) => {
    if (detailByListing[listingId] || loadingDetail[listingId]) return;
    setLoadingDetail((prev) => ({ ...prev, [listingId]: true }));
    try {
      const { data } = await getListingDetail(listingId);
      setDetailByListing((prev) => ({ ...prev, [listingId]: data }));
    } catch (error) {
      console.error(`Error fetching listing detail ${listingId}:`, error);
      setDetailByListing((prev) => ({ ...prev, [listingId]: { enchants: [], listing_options: [] } }));
    } finally {
      setLoadingDetail((prev) => ({ ...prev, [listingId]: false }));
    }
  };

  const toggleListing = (id) => {
    setExpandedListingIds((prev) => ({ ...prev, [id]: !prev[id] }));
    fetchListingDetail(id);
  };

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
      <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Package className="w-5 h-5 text-cyan-500" />
          {t('listings.title')}
        </h2>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={pagination.offset === 0}
          >
            {t('listings.prev')}
          </button>
          <span className="text-xs font-mono">
            {pagination.offset + 1} - {pagination.offset + listings.length}
          </span>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={listings.length < pagination.limit}
          >
            {t('listings.next')}
          </button>
          <button onClick={fetchListings} className="p-1 hover:text-cyan-400" title={t('listings.refresh')}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="divide-y divide-gray-700">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
          </div>
        ) : listings.length === 0 ? (
          <div className="px-6 py-8 text-center text-xs text-gray-500 uppercase tracking-wide">
            {t('listings.noListings')}
          </div>
        ) : (
          listings.map((listing) => {
            const isExpanded = !!expandedListingIds[listing.id];
            const detail = detailByListing[listing.id];
            const isDetailLoading = !!loadingDetail[listing.id];

            return (
              <div key={listing.id} className="transition-colors hover:bg-gray-700/30">
                <div
                  className="px-6 py-4 flex items-center justify-between cursor-pointer"
                  onClick={() => toggleListing(listing.id)}
                >
                  <div className="flex items-center gap-4">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-cyan-500" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-500" />
                    )}
                    <span className="text-lg font-black text-white">{listing.name || t('listings.unnamed')}</span>
                    {listing.prefix_enchant_name && (
                      <span className="text-xs font-bold text-blue-400 uppercase tracking-tighter">
                        {listing.prefix_enchant_name}
                      </span>
                    )}
                    {listing.suffix_enchant_name && (
                      <span className="text-xs font-bold text-red-400 uppercase tracking-tighter">
                        {listing.suffix_enchant_name}
                      </span>
                    )}
                    {listing.game_item_name && (
                      <span className="text-xs text-gray-400">
                        {listing.game_item_name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4">
                    {listing.price != null && (
                      <span className="text-sm font-bold text-yellow-400">
                        {t('listings.price', { price: Number(listing.price).toLocaleString() })}
                      </span>
                    )}
                    {listing.created_at && (
                      <span className="text-[10px] font-mono text-gray-500">
                        {new Date(listing.created_at).toLocaleString()}
                      </span>
                    )}
                    <span className="text-[10px] font-mono text-gray-500 bg-black/30 px-2 py-0.5 rounded">
                      ID: {listing.id}
                    </span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-16 py-4 bg-black/20 space-y-4">
                    {isDetailLoading ? (
                      <div className="py-4 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin text-gray-600" />
                          <span className="text-xs text-gray-600 uppercase">{t('listings.loadingDetails')}</span>
                        </div>
                      </div>
                    ) : detail ? (
                      <>
                        {(detail.item_type || detail.item_grade) && (
                          <div className="mb-3">
                            <p className="text-xs text-gray-400">
                              {[detail.item_type, detail.item_grade].filter(Boolean).join(' / ')}
                            </p>
                          </div>
                        )}

                        {(detail.erg_grade || detail.special_upgrade_type) && (
                          <div className="mb-3 flex flex-wrap gap-2">
                            {detail.erg_grade && (
                              <span className="text-xs px-2 py-1 bg-yellow-900/40 text-yellow-300 rounded">
                                ERG {detail.erg_grade}{detail.erg_level != null ? ` ${detail.erg_level}` : ''}
                              </span>
                            )}
                            {detail.special_upgrade_type && (
                              <span className={`text-xs px-2 py-1 rounded ${detail.special_upgrade_type === 'R' ? 'bg-pink-900/40 text-pink-300' : 'bg-cyan-900/40 text-cyan-300'}`}>
                                {detail.special_upgrade_type}강{detail.special_upgrade_level != null ? ` ${detail.special_upgrade_level}` : ''}
                              </span>
                            )}
                          </div>
                        )}

                        {(() => {
                          const attrs = Object.entries(ATTR_LABELS).filter(([k]) => detail[k] != null);
                          if (!attrs.length) return null;
                          return (
                            <div className="mb-3">
                              <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1 mb-2">
                                아이템 속성
                              </p>
                              <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                                {attrs.map(([k, label]) => (
                                  <div key={k} className="flex justify-between text-xs">
                                    <span className="text-gray-500">{label}</span>
                                    <span className="text-gray-300">{detail[k]}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })()}

                        {(detail.prefix_enchant || detail.suffix_enchant) && (
                          <div className="space-y-3">
                            <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1">
                              {t('listings.enchants')}
                            </p>
                            {[detail.prefix_enchant, detail.suffix_enchant].filter(Boolean).map((enc, idx) => (
                              <div key={idx} className="bg-gray-800/50 p-3 rounded-lg border border-gray-700/50">
                                <div className="flex items-center gap-3 mb-2">
                                  <span className={`text-xs font-bold uppercase px-1.5 py-0.5 rounded ${
                                    enc.slot === 0 ? 'bg-blue-900/50 text-blue-300' : 'bg-red-900/50 text-red-300'
                                  }`}>
                                    {enc.slot === 0 ? t('listings.prefix') : t('listings.suffix')}
                                  </span>
                                  <span className="text-sm font-bold text-white">{enc.enchant_name}</span>
                                  <span className="text-xs text-gray-500">{t('listings.rank', { rank: toRankLabel(enc.rank) })}</span>
                                </div>
                                {enc.effects?.length > 0 && (
                                  <ul className="space-y-1 ml-4">
                                    {enc.effects.map((eff, effIdx) => (
                                      <li key={effIdx} className="flex items-center gap-2">
                                        <span className="text-sm text-gray-300">{eff.raw_text}</span>
                                        {eff.value != null ? (
                                          <span className="text-xs font-bold text-cyan-400">
                                            = {eff.value}
                                          </span>
                                        ) : eff.min_value != null && (
                                          <span className="text-xs text-gray-500">
                                            = {eff.min_value === eff.max_value ? eff.min_value : `${eff.min_value}~${eff.max_value}`}
                                          </span>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {detail.listing_options?.length > 0 && (
                          <div className="space-y-3">
                            <p className="text-[10px] font-black text-gray-600 uppercase tracking-widest border-b border-gray-800 pb-1">
                              {t('listings.options')}
                            </p>
                            <ul className="space-y-2">
                              {detail.listing_options.map((opt, idx) => (
                                <li key={idx} className="bg-gray-800/50 p-3 rounded-lg border border-gray-700/50 flex items-center justify-between">
                                  <div className="flex items-center gap-3">
                                    <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">{opt.option_type}</span>
                                    <span className="text-sm font-medium text-gray-300">{opt.option_name}</span>
                                  </div>
                                  {opt.rolled_value != null && (
                                    <LevelBadge level={opt.rolled_value} maxLevel={opt.max_level}>
                                      {opt.rolled_value}{opt.max_level != null ? ` / ${opt.max_level}` : ''}
                                    </LevelBadge>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {detail.tags?.length > 0 && (
                          <div className="mb-3 flex flex-wrap gap-2">
                            {detail.tags.map((tag, idx) => (
                              <TagBadge key={idx} name={tag.name} weight={tag.weight} />
                            ))}
                          </div>
                        )}

                        {(!detail.prefix_enchant && !detail.suffix_enchant && !detail.listing_options?.length) && (
                          <p className="text-xs text-gray-600 uppercase">{t('listings.noEnchantReforge')}</p>
                        )}
                      </>
                    ) : null}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ListingsPanel;
