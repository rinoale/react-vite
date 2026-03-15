import React from 'react';
import LevelBadge from './LevelBadge';
import TagBadge from './TagBadge';
import PlayerName from './PlayerName';
import EchostoneIcon from './icons/EchostoneIcon';
import MuriasRelicIcon from './icons/MuriasRelicIcon';
import { ECHOSTONE_COLOR_MAP, getListingOptionDisplay, formatDate } from '../lib/listingUtils';

const enchantBadge = 'text-xs px-1.5 py-0.5 rounded bg-purple-900/50 text-purple-300 border border-purple-700/50';
const upgradeBadge = 'text-xs px-1.5 py-0.5 rounded bg-pink-900/50 text-pink-300 border border-pink-700/50';
const ergBadge = 'text-xs px-1.5 py-0.5 rounded bg-yellow-900/50 text-yellow-300 border border-yellow-700/50';

const ListingCard = ({ listing, selected = false, onClick }) => {
  const handleClick = React.useCallback(() => onClick(listing), [onClick, listing]);
  return (
    <div
      onClick={handleClick}
      className={`bg-gray-800 p-4 rounded-xl border cursor-pointer transition-all hover:scale-[1.02] ${selected ? 'border-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.3)]' : 'border-gray-700 hover:border-gray-600'}`}
    >
      {/* listing-title */}
      <h3 className="font-bold text-lg leading-tight mb-1">{listing.name}</h3>
      {/* listing-specs */}
      <div className="flex flex-wrap items-center gap-1.5 mb-1">
        {listing.prefix_enchant_name && (
          <span className={enchantBadge}>{listing.prefix_enchant_name}</span>
        )}
        {listing.suffix_enchant_name && (
          <span className={enchantBadge}>{listing.suffix_enchant_name}</span>
        )}
        {listing.game_item_name && (
          <span className="text-sm text-gray-300">{listing.game_item_name}</span>
        )}
        {listing.special_upgrade_type && (
          <span className={upgradeBadge}>
            {listing.special_upgrade_type}{listing.special_upgrade_level != null ? listing.special_upgrade_level : ''}
          </span>
        )}
        {listing.erg_grade && (
          <span className={ergBadge}>
            {listing.erg_grade}{listing.erg_level != null ? ` ${listing.erg_level}` : ''}
          </span>
        )}
      </div>
      {/* listing-options */}
      {listing.listing_options?.filter(o => o.option_type !== 'enchant_effects').map((opt, idx) => (
        <div key={idx} className="flex items-center gap-1.5 text-sm mb-0.5">
          {opt.option_type === 'echostone_options' && (
            <EchostoneIcon color={ECHOSTONE_COLOR_MAP[listing.game_item_name] || 'red'} className="w-4 h-4" />
          )}
          {opt.option_type === 'murias_relic_options' && (
            <MuriasRelicIcon className="w-4 h-4" />
          )}
          <span className="text-cyan-300">{getListingOptionDisplay(opt, listing.game_item_name)}</span>
          {opt.rolled_value != null && (
            <LevelBadge level={opt.rolled_value} maxLevel={opt.max_level}>
              {opt.rolled_value}{opt.max_level != null ? `/${opt.max_level}` : ''}
            </LevelBadge>
          )}
        </div>
      ))}
      {/* listing-tags */}
      {listing.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {listing.tags.map((tag, idx) => (
            <TagBadge key={idx} name={tag.name} weight={tag.weight} />
          ))}
        </div>
      )}
      {/* listing-seller */}
      <p className="text-xs text-gray-500">
        <PlayerName server={listing.seller_server} gameId={listing.seller_game_id} verified={listing.seller_verified} />
        {listing.created_at && (
          <span className="ml-2">{formatDate(listing.created_at)}</span>
        )}
      </p>
    </div>
  );
};

export default React.memo(ListingCard);
