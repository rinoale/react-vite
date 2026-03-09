import React, { useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useListingSearch } from '@mabi/shared/hooks/useListingSearch';
import ListingSearchBar from '@mabi/shared/components/ListingSearchBar';

const searchBarClass = 'flex items-center gap-1.5 flex-wrap bg-gray-800 border border-gray-700 rounded-xl py-3 pl-12 pr-8 min-h-[3rem] focus-within:ring-2 focus-within:ring-cyan-500';

const SearchPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tagWeightsRef = useRef({});

  const handleSubmit = useCallback(({ tags, text }) => {
    navigate('/market', { state: { tags, text, tagWeights: tagWeightsRef.current } });
  }, [navigate]);

  const handleSelectListing = useCallback((listing) => {
    navigate('/market', { state: { listingId: listing.id } });
  }, [navigate]);

  const search = useListingSearch({
    onSubmit: handleSubmit,
    onSelectListing: handleSelectListing,
  });

  tagWeightsRef.current = search.tagWeights;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col items-center p-6 pt-24">
      <h1 className="text-4xl font-black text-center text-white tracking-tight mb-8">
        {t('search.title', 'Item Search')}
      </h1>

      <div className="w-full max-w-lg">
        <ListingSearchBar
          search={search}
          wrapperClassName="relative w-full"
          barClassName={searchBarClass}
          placeholder={t('search.placeholder', 'Search items, tags...')}
        />
      </div>
    </div>
  );
};

export default SearchPage;
