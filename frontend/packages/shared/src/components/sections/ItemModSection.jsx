import React, { useState, useCallback } from 'react';
import { AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import DefaultSection from './DefaultSection';
import CustomSelect from '../CustomSelect';
import { editNumber } from '../../styles';

const TYPES = ['R', 'S'];
const MAX_LEVEL = 8;

const TYPE_OPTIONS = TYPES.map((tp) => ({ value: tp, label: tp }));

const NumberField = ({ value, onCommit, placeholder }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const commit = (raw) => {
    setEditing(false);
    onCommit(raw);
  };

  if (editing) {
    return (
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
        className={editNumber}
      />
    );
  }

  return (
    <span
      className="text-orange-400 font-bold cursor-pointer hover:underline"
      onClick={() => { setDraft(value != null ? String(value) : ''); setEditing(true); }}
    >
      {value ?? placeholder ?? '?'}
    </span>
  );
};

const SpecialUpgradeRow = ({ type, level, onLineChange }) => {
  const { t } = useTranslation();
  const needsCorrection = type === null || level === null;

  const update = (newType, newLevel) => {
    onLineChange(-1, '', (sec) => {
      sec.special_upgrade_type = newType;
      sec.special_upgrade_level = newLevel;
    });
  };

  const handleTypeChange = useCallback((val) => {
    update(val || null, level);
  }, [level]);

  const typeColor = needsCorrection ? 'text-amber-300' : (type === 'S' ? 'text-cyan-300' : 'text-pink-300');
  const textColor = needsCorrection ? 'text-amber-200' : 'text-gray-300';

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
        <CustomSelect
          value={type || ''}
          onChange={handleTypeChange}
          options={TYPE_OPTIONS}
          placeholder="—"
          variant="inline"
          triggerClassName={`${typeColor} font-bold`}
        />
        {' ('}
        <NumberField
          value={level}
          onCommit={(raw) => {
            const n = parseInt(raw, 10);
            if (!isNaN(n)) update(type, Math.max(1, Math.min(MAX_LEVEL, n)));
          }}
          placeholder="—"
        />
        {t('sections.item_mod.levelSuffix') + ')'}
      </p>
    </div>
  );
};

const ItemModSection = ({ lines, has_special_upgrade, special_upgrade_type, special_upgrade_level, onLineChange }) => {
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
