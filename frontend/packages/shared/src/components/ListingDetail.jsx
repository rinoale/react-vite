import React, { useState, useCallback, useRef } from 'react';
import { Wand2, MessageCircle, Share2, Check } from 'lucide-react';
import { badgeYellow, badgePink, cardSlot } from '../styles';
import { useTranslation } from 'react-i18next';
import LevelBadge from './LevelBadge';
import TagBadge from './TagBadge';
import PlayerName from './PlayerName';
import { ATTR_LABELS, SLOT_LABELS, getOptionIcon, getListingOptionDisplay, renderRolledEffect } from '../lib/listingUtils';

const ListingDetail = ({ detail, onTagClick }) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const timerRef = useRef(null);

  const handleShare = useCallback(() => {
    if (!detail.short_code) return;
    const url = `${window.location.origin}/l/${detail.short_code}`;
    navigator.clipboard?.writeText(url);
    setCopied(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), 1500);
  }, [detail.short_code]);

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <div className="flex items-start justify-between gap-2 mb-1">
        <h2 className="text-2xl font-bold">{detail.name}</h2>
        {detail.short_code && (
          <button type="button" onClick={handleShare} className="shrink-0 mt-1 p-1.5 rounded text-gray-500 hover:text-gray-300 hover:bg-gray-700 transition-colors" title={t('listing.share', 'Share')}>
            {copied ? <Check className="w-4 h-4 text-green-400" /> : <Share2 className="w-4 h-4" />}
          </button>
        )}
      </div>
      {detail.game_item_name && (
        <p className="text-sm text-gray-400 mb-2">{detail.game_item_name}</p>
      )}
      {detail.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {detail.tags.map((tag, idx) => (
            <TagBadge
              key={idx}
              name={tag.name}
              weight={tag.weight}
              onClick={tag.weight > 0 && onTagClick ? () => onTagClick(tag.name, tag.weight) : undefined}
            />
          ))}
        </div>
      )}

      {detail.description && (
        <p className="text-sm text-gray-400 mb-4">{detail.description}</p>
      )}

      {/* Item Attrs */}
      {(() => {
        const attrs = Object.entries(ATTR_LABELS).filter(([k]) => detail[k] != null);
        if (!attrs.length) return null;
        return (
          <div className="mb-4">
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {attrs.map(([k, label]) => (
                <div key={k} className="flex justify-between text-xs">
                  <span className="text-gray-500">{label}</span>
                  <span className="text-gray-200">{detail[k]}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* Enchants */}
      {(detail.prefix_enchant || detail.suffix_enchant) && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-purple-400 mb-2 flex items-center gap-1">
            <Wand2 className="w-4 h-4" />
            {t('marketplace.enchantLabel')}
          </h3>
          <div className="space-y-2">
            {[detail.prefix_enchant, detail.suffix_enchant].filter(Boolean).map((enc, idx) => (
              <div key={idx} className={cardSlot}>
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-medium text-purple-300">{enc.enchant_name}</span>
                  <span className="text-xs text-gray-400">{SLOT_LABELS[enc.slot] || enc.slot}</span>
                </div>
                {enc.effects?.length > 0 && (
                  <ul className="space-y-0.5">
                    {enc.effects.map((eff, i) => (
                      <li key={i} className="text-xs text-gray-400">
                        {renderRolledEffect(eff)}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Listing Options grouped by type */}
      {(() => {
        const opts = (detail.listing_options || []).filter(o => o.option_type !== 'enchant_effects');
        if (!opts.length) return null;
        const grouped = opts.reduce((acc, o) => { (acc[o.option_type] ??= []).push(o); return acc; }, {});
        return Object.entries(grouped).map(([type, items]) => (
          <div key={type} className="mb-4">
            <h3 className="text-sm font-semibold text-cyan-400 mb-2 flex items-center gap-1">
              {getOptionIcon(type, detail.game_item_name)}
              {t(`marketplace.optionType.${type}`)}
            </h3>
            <div className="space-y-2">
              {items.map((opt, idx) => (
                <div key={idx} className={`${cardSlot} flex justify-between items-center`}>
                  <span className="text-sm text-cyan-300">{getListingOptionDisplay(opt, detail.game_item_name)}</span>
                  {opt.rolled_value != null && (
                    <LevelBadge level={opt.rolled_value} maxLevel={opt.max_level}>
                      {opt.rolled_value}{opt.max_level != null ? ` / ${opt.max_level}` : ''}
                    </LevelBadge>
                  )}
                </div>
              ))}
            </div>
          </div>
        ));
      })()}

      {/* Special Upgrade */}
      {detail.special_upgrade_type && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-pink-400 mb-2">{t('marketplace.specialUpgradeLabel')}</h3>
          <div className={`${cardSlot} flex justify-between items-center`}>
            <span className="text-sm text-pink-300">
              {t(`marketplace.specialUpgrade${detail.special_upgrade_type}`)}
            </span>
            {detail.special_upgrade_level != null && (
              <span className={badgePink}>
                {t('marketplace.specialUpgradeLevel', { level: detail.special_upgrade_level })}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Erg */}
      {detail.erg_grade && (
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-yellow-400 mb-2">{t('marketplace.ergLabel')}</h3>
          <div className={`${cardSlot} flex justify-between items-center`}>
            <span className="text-sm text-yellow-300">{t('marketplace.ergGrade', { grade: detail.erg_grade })}</span>
            {detail.erg_level != null && (
              <span className={badgeYellow}>
                {detail.erg_level}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Seller */}
      {(detail.seller_server || detail.seller_game_id) && (
        <div className="mt-6 pt-4 border-t border-gray-700 flex items-center justify-between">
          <PlayerName server={detail.seller_server} gameId={detail.seller_game_id} verified={detail.seller_verified} className="text-sm" />
          {detail.seller_discord_id && (
            <a
              href={`https://discord.com/users/${detail.seller_discord_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
            >
              <MessageCircle className="w-3.5 h-3.5" />
              DM
            </a>
          )}
        </div>
      )}
    </div>
  );
};

export default ListingDetail;
