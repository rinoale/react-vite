import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import DefaultSection from './DefaultSection';

const TYPES = ['R', 'S'];
const MAX_LEVEL = 8;

const inlineSelect = 'appearance-none bg-transparent border-none outline-none cursor-pointer text-center';
const inlineInput = 'bg-transparent border-none outline-none text-center text-orange-400 font-medium w-5';

const SpecialUpgradeRow = ({ type, level, onLineChange }) => {
  const { t } = useTranslation();
  const [levelDraft, setLevelDraft] = useState(null);
  const needsCorrection = type === null || level === null;

  const update = (newType, newLevel) => {
    onLineChange(-1, '', (sec) => {
      sec.special_upgrade_type = newType;
      sec.special_upgrade_level = newLevel;
    });
  };

  const commitLevel = (raw) => {
    setLevelDraft(null);
    const n = parseInt(raw, 10);
    if (!isNaN(n)) update(type, Math.max(1, Math.min(MAX_LEVEL, n)));
  };

  const typeColor = needsCorrection ? 'text-amber-300' : (type === 'S' ? 'text-cyan-300' : 'text-pink-300');
  const textColor = needsCorrection ? 'text-amber-200' : 'text-gray-300';
  const inputColor = needsCorrection ? `${inlineInput} text-amber-300` : inlineInput;

  return (
    <div className="p-2">
      {needsCorrection && (
        <div className="flex items-center gap-1.5 mb-1">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <p className="text-xs text-amber-300">{t('sections.item_mod.unrecognized')}</p>
        </div>
      )}
      <p className={`text-sm font-medium ${textColor}`}>
        {t('sections.item_mod.label') + ' '}
        <select
          value={type || ''}
          onChange={(e) => update(e.target.value || null, level)}
          className={`${inlineSelect} ${typeColor} font-bold w-4`}
        >
          {!type && <option value="">—</option>}
          {TYPES.map(tp => <option key={tp} value={tp} className="text-gray-300 bg-gray-900">{tp}</option>)}
        </select>
        {' ('}
        <input
          type="text"
          value={levelDraft ?? level ?? ''}
          onChange={(e) => setLevelDraft(e.target.value)}
          onBlur={(e) => commitLevel(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') commitLevel(e.target.value); }}
          className={inputColor}
          placeholder="—"
        />
        {t('sections.item_mod.levelSuffix') + ')'}
      </p>
    </div>
  );
};

const ItemModSection = ({ lines, has_special_upgrade, special_upgrade_type, special_upgrade_level, onLineChange }) => {
  // When special upgrade fields exist, the first line is the pink OCR text — replace with structured UI
  // When special upgrade detected, the first line is the pink OCR text — replace with structured UI
  const remainingLines = has_special_upgrade ? (lines || []).slice(1) : lines;

  return (
    <div className="space-y-2">
      {has_special_upgrade && (
        <SpecialUpgradeRow
          type={special_upgrade_type ?? null}
          level={special_upgrade_level ?? null}
          onLineChange={onLineChange}
        />
      )}
      {remainingLines?.length > 0 && (
        <DefaultSection lines={remainingLines} onLineChange={onLineChange} />
      )}
    </div>
  );
};

export default ItemModSection;
