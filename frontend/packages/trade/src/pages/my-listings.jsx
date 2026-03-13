import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Package, Loader2, Plus, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getMyListings, getListingDetail, updateListingStatus } from '@mabi/shared/api/listings';
import ListingCard from '@mabi/shared/components/ListingCard';
import ListingDetail from '@mabi/shared/components/ListingDetail';

const PAGE_SIZE = 50;

const STATUS_OPTIONS = [
  { value: 0, key: 'myListings.statusDraft', cls: 'bg-gray-600 text-gray-200' },
  { value: 1, key: 'myListings.statusListed', cls: 'bg-green-800 text-green-200' },
  { value: 2, key: 'myListings.statusSold', cls: 'bg-blue-800 text-blue-200' },
  { value: 3, key: 'myListings.statusDeleted', cls: 'bg-red-900 text-red-200' },
];

const TABS = [
  { value: null, key: 'myListings.tabAll' },
  { value: 0, key: 'myListings.statusDraft' },
  { value: 1, key: 'myListings.statusListed' },
  { value: 2, key: 'myListings.statusSold' },
];

const statusSelectBase = 'text-[10px] font-bold pl-1.5 pr-5 py-0.5 rounded border-none outline-none cursor-pointer appearance-none';
const tabBase = 'px-4 py-1.5 text-sm font-medium rounded-lg transition-colors';
const tabActive = 'bg-gray-700 text-white';
const tabInactive = 'text-gray-500 hover:text-gray-300 hover:bg-gray-800';
const modalOverlay = 'fixed inset-0 z-50 flex items-center justify-center bg-black/60';
const modalCard = 'bg-gray-800 rounded-lg border border-gray-700 p-6 shadow-xl max-w-sm w-full mx-4';
const modalBtn = 'px-4 py-2 text-sm font-medium rounded transition-colors';

const MyListings = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [listings, setListings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(null);
  const [selectedListing, setSelectedListing] = useState(null);
  const [listingDetail, setListingDetail] = useState(null);
  const [hasMore, setHasMore] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [confirmModal, setConfirmModal] = useState(null);
  const sentinelRef = useRef(null);

  const fetchPage = useCallback(async (offset) => {
    try {
      const { data } = await getMyListings({ limit: PAGE_SIZE, offset });
      setHasMore(data.length >= PAGE_SIZE);
      return data;
    } catch {
      setHasMore(false);
      return [];
    }
  }, []);

  useEffect(() => {
    fetchPage(0).then((data) => {
      setListings(data);
      setLoading(false);
    });
  }, [fetchPage]);

  const filteredListings = useMemo(() => {
    if (activeTab === null) return listings;
    return listings.filter((l) => l.status === activeTab);
  }, [listings, activeTab]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    const data = await fetchPage(listings.length);
    if (data.length > 0) setListings((prev) => [...prev, ...data]);
    setLoadingMore(false);
  }, [loadingMore, hasMore, listings.length, fetchPage]);

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

  const handleSelect = useCallback((listing) => {
    setSelectedListing(listing);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setSelectedListing(null);
  }, []);

  const handleNewListing = useCallback(() => {
    navigate('/sell');
  }, [navigate]);

  const handleStatusSelect = useCallback((listingId, newStatus, e) => {
    e.stopPropagation();
    const listing = listings.find((l) => l.id === listingId);
    if (!listing || listing.status === newStatus) return;
    const opt = STATUS_OPTIONS.find((s) => s.value === newStatus);
    setConfirmModal({ listingId, newStatus, listingName: listing.name, statusKey: opt?.key });
  }, [listings]);

  const handleConfirm = useCallback(async () => {
    if (!confirmModal) return;
    const { listingId, newStatus } = confirmModal;
    setConfirmModal(null);
    try {
      await updateListingStatus(listingId, newStatus);
      if (newStatus === 3) {
        setListings((prev) => prev.filter((l) => l.id !== listingId));
        if (selectedListing?.id === listingId) setSelectedListing(null);
      } else {
        setListings((prev) => prev.map((l) => l.id === listingId ? { ...l, status: newStatus } : l));
      }
    } catch {
      // silent
    }
  }, [confirmModal, selectedListing]);

  const handleCancelConfirm = useCallback(() => {
    setConfirmModal(null);
  }, []);

  useEffect(() => {
    if (selectedListing) {
      getListingDetail(selectedListing.id)
        .then(({ data }) => setListingDetail(data))
        .catch(() => setListingDetail(null));
    } else {
      setListingDetail(null);
    }
  }, [selectedListing]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-gray-500 animate-spin" />
      </div>
    );
  }

  return (
    <div id="my-listings-page" className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-screen-2xl mx-auto">
        {/* header */}
        <div id="my-listings-header" className="flex items-center justify-between mb-4">
          <h1 className="text-3xl font-bold text-cyan-400 flex items-center gap-2">
            <Package className="w-8 h-8" />
            {t('myListings.title')}
          </h1>
          <button type="button" onClick={handleNewListing} className="flex items-center gap-1.5 text-sm px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-500 text-white font-semibold transition-colors">
            <Plus className="w-4 h-4" />
            {t('myListings.newListing')}
          </button>
        </div>

        {/* tabs */}
        <div id="my-listings-tabs" className="flex gap-1 mb-6">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={`${tabBase} ${activeTab === tab.value ? tabActive : tabInactive}`}
            >
              {t(tab.key)}
            </button>
          ))}
        </div>

        {filteredListings.length === 0 ? (
          <div id="my-listings-empty" className="bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-12 text-center text-gray-500 flex flex-col items-center">
            <Package className="w-12 h-12 mb-4 opacity-50" />
            <p className="mb-4">{listings.length === 0 ? t('myListings.empty') : t('myListings.noResults')}</p>
            {listings.length === 0 && (
              <button type="button" onClick={handleNewListing} className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors">
                {t('myListings.createFirst')}
              </button>
            )}
          </div>
        ) : (
          <div id="my-listings-content" className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
            {/* listing-grid */}
            <div id="my-listings-grid" className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4 items-start">
              {filteredListings.map((listing) => {
                const opt = STATUS_OPTIONS.find((s) => s.value === listing.status) || STATUS_OPTIONS[0];
                return (
                  <div key={listing.id} className="relative">
                    {/* status-select */}
                    <div className="absolute top-2 right-2 z-10">
                      <select
                        value={listing.status}
                        onChange={(e) => handleStatusSelect(listing.id, Number(e.target.value), e)}
                        onClick={(e) => e.stopPropagation()}
                        className={`${statusSelectBase} ${opt.cls}`}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s.value} value={s.value}>{t(s.key)}</option>
                        ))}
                      </select>
                    </div>
                    <ListingCard
                      listing={listing}
                      selected={selectedListing?.id === listing.id}
                      onClick={() => handleSelect(listing)}
                    />
                  </div>
                );
              })}
              {hasMore && filteredListings.length > 0 && (
                <div ref={sentinelRef} className="md:col-span-2 flex justify-center py-4">
                  {loadingMore && <Loader2 className="w-6 h-6 text-gray-500 animate-spin" />}
                </div>
              )}
            </div>

            {/* detail-panel (desktop) */}
            <div id="my-listings-detail" className="hidden lg:block lg:col-span-1 sticky top-6 max-h-[calc(100vh-6rem)] overflow-y-auto">
              {selectedListing && listingDetail ? (
                <ListingDetail detail={listingDetail} />
              ) : (
                <div className="bg-gray-800/50 border border-gray-700 border-dashed rounded-xl p-8 text-center text-gray-500 flex flex-col items-center">
                  <Package className="w-12 h-12 mb-4 opacity-50" />
                  <p>{t('myListings.selectListing')}</p>
                </div>
              )}
            </div>

            {/* detail-panel (mobile) */}
            {selectedListing && listingDetail && (
              <div id="my-listings-detail-mobile" className="lg:hidden fixed inset-0 z-40 flex">
                <div className="absolute inset-0 bg-black/60" onClick={handleCloseDetail} />
                <div className="relative ml-auto w-full max-w-md bg-gray-900 overflow-y-auto">
                  <button
                    type="button"
                    className="sticky top-0 z-10 w-full flex items-center gap-2 px-4 py-3 bg-gray-900 border-b border-gray-700 text-sm text-gray-400 hover:text-gray-200 transition-colors"
                    onClick={handleCloseDetail}
                  >
                    <X className="w-4 h-4" />
                    {t('marketplace.backToList', 'Back')}
                  </button>
                  <div className="p-4">
                    <ListingDetail detail={listingDetail} />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* status-confirm-modal */}
      {confirmModal && (
        <div className={modalOverlay}>
          <div className={modalCard}>
            <p className="text-sm text-gray-200 mb-4">
              {t('myListings.confirmStatusChange', {
                name: confirmModal.listingName,
                status: t(confirmModal.statusKey),
              })}
            </p>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={handleCancelConfirm} className={`${modalBtn} bg-gray-700 text-gray-300 hover:bg-gray-600`}>
                {t('sections.cancel')}
              </button>
              <button type="button" onClick={handleConfirm} className={`${modalBtn} bg-cyan-600 text-white hover:bg-cyan-500`}>
                {t('myListings.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MyListings;
