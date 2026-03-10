import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { ShoppingBag, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getListings, getListingDetail, searchListings } from '@mabi/shared/api/recommend';
import { useListingSearch } from '@mabi/shared/hooks/useListingSearch';
import ListingSearchBar from '@mabi/shared/components/ListingSearchBar';
import ListingCard from '@mabi/shared/components/ListingCard';
import ListingDetail from '@mabi/shared/components/ListingDetail';

const PAGE_SIZE = 50;

const Marketplace = () => {
  const { t } = useTranslation();
  const [listings, setListings] = useState([]);
  const [selectedListing, setSelectedListing] = useState(null);
  const [listingDetail, setListingDetail] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const sentinelRef = useRef(null);
  const searchStateRef = useRef({ tags: [], text: '' });

  // --- Fetch a page of listings, returns the fetched data ---
  const fetchPage = useCallback(async (offset, tags, text) => {
    const pagination = { limit: PAGE_SIZE, offset };
    try {
      let data;
      if (text || tags?.length) {
        const res = await searchListings(text || '', tags?.length ? tags : undefined, pagination);
        data = res.data;
      } else {
        const res = await getListings(pagination);
        data = res.data;
      }
      setHasMore(data.length >= PAGE_SIZE);
      return data;
    } catch (error) {
      console.error("Failed to fetch listings:", error);
      setHasMore(false);
      return [];
    }
  }, []);

  // --- Load next page (called by IntersectionObserver) ---
  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    const { tags, text } = searchStateRef.current;
    const data = await fetchPage(listings.length, tags, text);
    if (data.length > 0) {
      setListings((prev) => [...prev, ...data]);
    }
    setLoadingMore(false);
  }, [loadingMore, hasMore, listings.length, fetchPage]);

  // --- IntersectionObserver for infinite scroll ---
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) loadMore(); },
      { rootMargin: '200px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  const fetchDetail = useCallback(async (listingId) => {
    try {
      const { data } = await getListingDetail(listingId);
      setListingDetail(data);
    } catch (error) {
      console.error("Failed to fetch listing detail:", error);
      setListingDetail(null);
    }
  }, []);

  const handleSearchResults = useCallback((data, { tags, text } = {}) => {
    setListings(data);
    setHasMore(data.length >= PAGE_SIZE);
    if (tags !== undefined || text !== undefined) {
      searchStateRef.current = { tags: tags || [], text: text || '' };
    }
  }, []);

  const handleSearchClear = useCallback(async () => {
    setSelectedListing(null);
    searchStateRef.current = { tags: [], text: '' };
    const data = await fetchPage(0, [], '');
    setListings(data);
  }, [fetchPage]);

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

      searchStateRef.current = { tags, text: name };
      const data = await fetchPage(0, tags.length ? tags : [], name);
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

  return (
    <div id="marketplace-page" className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-screen-2xl mx-auto">
        {/* Header */}
        <div id="marketplace-header" className="sticky top-0 z-10 bg-gray-900 pb-4 flex flex-col md:flex-row justify-between items-center mb-4 gap-4">
          <h1 className="text-3xl font-bold text-cyan-400 flex items-center gap-2">
            <ShoppingBag className="w-8 h-8" />
            {t('marketplace.title')}
          </h1>

          <ListingSearchBar search={search} />
        </div>

        <div id="marketplace-content" className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          {/* Listing Grid */}
          <div id="listing-grid" className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
            {listings.length > 0 ? (
              listings.map(listing => (
                <ListingCard
                  key={listing.id}
                  listing={listing}
                  selected={selectedListing?.id === listing.id}
                  onClick={() => handleSelectListing(listing)}
                />
              ))
            ) : (
              <div id="listing-empty" className="md:col-span-2 bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-12 text-center text-gray-500 flex flex-col items-center">
                <ShoppingBag className="w-12 h-12 mb-4 opacity-50" />
                <p>{listings.length === 0 ? t('marketplace.noListings') : t('marketplace.noResults')}</p>
              </div>
            )}
            {/* Infinite scroll sentinel */}
            {hasMore && listings.length > 0 && (
              <div ref={sentinelRef} className="md:col-span-2 flex justify-center py-4">
                {loadingMore && <Loader2 className="w-6 h-6 text-gray-500 animate-spin" />}
              </div>
            )}
          </div>

          {/* Sidebar: Listing Detail */}
          <div id="listing-detail-panel" className="lg:col-span-1 sticky top-20 max-h-[calc(100vh-6rem)] overflow-y-auto">
            {selectedListing && listingDetail ? (
              <ListingDetail
                detail={listingDetail}
                onTagClick={search.handleSelectTag}
              />
            ) : (
              <div id="listing-detail-empty" className="bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-8 text-center text-gray-500 flex flex-col items-center">
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
