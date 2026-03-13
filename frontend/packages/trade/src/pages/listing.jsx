import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ShoppingBag, Share2, Check, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getListingByCode } from '@mabi/shared/api/listings';
import ListingDetail from '@mabi/shared/components/ListingDetail';

const ListingPage = () => {
  const { code } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    getListingByCode(code)
      .then(({ data }) => { if (!cancelled) setDetail(data); })
      .catch(() => { if (!cancelled) setNotFound(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [code]);

  const handleShare = useCallback(() => {
    const url = window.location.href;
    navigator.clipboard?.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, []);

  const handleBrowse = useCallback(() => {
    navigate('/market');
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-gray-500 animate-spin" />
      </div>
    );
  }

  if (notFound || !detail) {
    return (
      <div className="min-h-screen bg-gray-900 text-gray-100 flex flex-col items-center justify-center gap-4">
        <ShoppingBag className="w-16 h-16 text-gray-600" />
        <p className="text-gray-400">{t('marketplace.listingNotFound', 'Listing not found')}</p>
        <button type="button" onClick={handleBrowse} className="text-sm text-cyan-400 hover:text-cyan-300 transition-colors">
          {t('marketplace.browseMarketplace', 'Browse Marketplace')}
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-6">
      <div className="max-w-lg mx-auto">
        {/* share bar */}
        <div className="flex items-center justify-between mb-4">
          <button type="button" onClick={handleBrowse} className="text-sm text-gray-400 hover:text-gray-200 transition-colors">
            <ShoppingBag className="w-5 h-5 inline mr-1.5 align-text-bottom" />
            {t('marketplace.title')}
          </button>
          <button type="button" onClick={handleShare} className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors">
            {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Share2 className="w-3.5 h-3.5" />}
            {copied ? t('listing.copied', 'Copied!') : t('listing.share', 'Share')}
          </button>
        </div>

        <ListingDetail detail={detail} />
      </div>
    </div>
  );
};

export default ListingPage;
