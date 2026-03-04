import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import DefaultSection from './DefaultSection';

const TYPES = ['R', 'S'];
const LEVELS = [1, 2, 3, 4, 5, 6, 7, 8];

const SpecialUpgradeRow = ({ type, level, onLineChange }) => {
  const { t } = useTranslation();
  const needsCorrection = type === null || level === null;

  const update = (newType, newLevel) => {
    onLineChange(-1, '', (sec) => {
      sec.special_upgrade_type = newType;
      sec.special_upgrade_level = newLevel;
    });
  };

  if (needsCorrection) {
    return (
      <div className="flex items-start gap-2 p-2 rounded border border-amber-700/50 bg-amber-900/20">
        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <div className="flex-1 space-y-2">
          <p className="text-xs text-amber-300">{t('sections.item_mod.unrecognized')}</p>
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-400">{t('sections.item_mod.typeLabel')}</label>
            <select
              value={type || ''}
              onChange={(e) => update(e.target.value || null, level)}
              className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 outline-none focus:ring-1 focus:ring-amber-500"
            >
              <option value="">—</option>
              {TYPES.map(tp => <option key={tp} value={tp}>{tp}</option>)}
            </select>
            <label className="text-xs text-gray-400">{t('sections.item_mod.levelLabel')}</label>
            <select
              value={level ?? ''}
              onChange={(e) => update(type, e.target.value ? parseInt(e.target.value, 10) : null)}
              className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 outline-none focus:ring-1 focus:ring-amber-500"
            >
              <option value="">—</option>
              {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
        </div>
      </div>
    );
  }

  // Successfully extracted — show formatted "특별개조 R (7단계)" with inline edit
  return (
    <div className="flex items-center gap-2 p-2 rounded border border-pink-700/50 bg-pink-900/20">
      <span className="text-sm font-medium text-pink-300">
        특별 개조 {type} ({level}단계)
      </span>
      <div className="flex items-center gap-2 ml-auto">
        <select
          value={type}
          onChange={(e) => update(e.target.value, level)}
          className="bg-gray-900 border border-gray-700 rounded px-1.5 py-0.5 text-xs text-gray-300 outline-none focus:ring-1 focus:ring-pink-500"
        >
          {TYPES.map(tp => <option key={tp} value={tp}>{tp}</option>)}
        </select>
        <select
          value={level}
          onChange={(e) => update(type, parseInt(e.target.value, 10))}
          className="bg-gray-900 border border-gray-700 rounded px-1.5 py-0.5 text-xs text-gray-300 outline-none focus:ring-1 focus:ring-pink-500"
        >
          {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
      </div>
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
