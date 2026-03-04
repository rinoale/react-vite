import React from 'react';
import { useTranslation } from 'react-i18next';

const ATTR_KEYS = [
  'damage', 'magic_damage', 'additional_damage', 'balance',
  'defense', 'protection', 'magic_defense', 'magic_protection',
  'durability',
];

const ItemAttrsSection = ({ attrs, onAttrsChange }) => {
  const { t } = useTranslation();

  if (!attrs || Object.keys(attrs).length === 0) {
    return <p className="text-xs text-gray-500 italic">No attributes detected</p>;
  }

  const presentKeys = ATTR_KEYS.filter(k => k in attrs);

  return (
    <div className="space-y-2">
      {presentKeys.map((key) => (
        <div key={key} className="flex items-center gap-3">
          <label className="text-xs text-gray-400 w-24 shrink-0 text-right">
            {t(`attrs.${key}`, key)}
          </label>
          <input
            type="text"
            value={attrs[key] || ''}
            onChange={(e) => onAttrsChange({ ...attrs, [key]: e.target.value })}
            className="flex-1 bg-gray-900 border border-gray-700 focus:border-orange-500 rounded px-3 py-1.5 text-sm text-gray-300 outline-none transition-colors"
          />
        </div>
      ))}
    </div>
  );
};

export default ItemAttrsSection;
