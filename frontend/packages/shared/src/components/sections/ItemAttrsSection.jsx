import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

const ATTR_KEYS = [
  'damage', 'magic_damage', 'additional_damage', 'balance',
  'defense', 'protection', 'magic_defense', 'magic_protection',
  'durability',
];

const AttrRow = ({ label, value, onChange }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const commit = (raw) => {
    setEditing(false);
    if (raw !== value) onChange(raw);
  };

  return (
    <div className="flex items-center gap-1 text-xs text-gray-400">
      <span>{label}</span>
      {editing ? (
        <input
          type="text"
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => commit(draft)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit(draft);
            if (e.key === 'Escape') setEditing(false);
          }}
          className="w-12 text-orange-400 font-bold bg-gray-900 border border-orange-500 rounded px-1 text-xs text-center outline-none"
        />
      ) : (
        <span
          className="text-orange-400 font-bold cursor-pointer hover:underline"
          onClick={() => { setDraft(value || ''); setEditing(true); }}
        >
          {value || '?'}
        </span>
      )}
    </div>
  );
};

const ItemAttrsSection = ({ attrs, onAttrsChange }) => {
  const { t } = useTranslation();

  if (!attrs || Object.keys(attrs).length === 0) {
    return <p className="text-xs text-gray-500 italic">No attributes detected</p>;
  }

  const presentKeys = ATTR_KEYS.filter(k => k in attrs);

  return (
    <div className="space-y-1.5">
      {presentKeys.map((key) => (
        <AttrRow
          key={key}
          label={t(`attrs.${key}`, key)}
          value={attrs[key]}
          onChange={(val) => onAttrsChange({ ...attrs, [key]: val })}
        />
      ))}
    </div>
  );
};

export default ItemAttrsSection;
