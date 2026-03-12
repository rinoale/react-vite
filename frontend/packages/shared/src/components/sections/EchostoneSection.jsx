import React, { useState, useMemo } from 'react';
import { Pencil } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ConfigSearchInput from '../ConfigSearchInput';
import { cardItem, groupRow, flexCenter, iconBtnEdit, editLevelCyan, badgeClickable } from '../../styles';
import LevelBadge from '../LevelBadge';

const EchostoneSection = ({ echostoneType, options, onOptionsChange }) => {
  const { t } = useTranslation();
  const [editingName, setEditingName] = useState(false);
  const [editingLevel, setEditingLevel] = useState(false);
  const [levelDraft, setLevelDraft] = useState('');

  const items = useMemo(
    () => (window.ECHOSTONE_CONFIG || []).filter(e => e.type === echostoneType),
    [echostoneType],
  );

  const opt = options[0] || null;

  const handleSelect = (item) => {
    onOptionsChange([{
      option_name: item.option_name,
      option_id: item.id,
      echostone_type: echostoneType,
      level: item.min_level || 1,
      min_level: item.min_level || 1,
      max_level: item.max_level || 20,
    }]);
    setEditingName(false);
  };

  const commitLevel = (value) => {
    setEditingLevel(false);
    if (!opt || value === '' || value === String(opt.level)) return;
    const num = parseInt(value, 10);
    if (isNaN(num)) return;
    const clamped = Math.max(opt.min_level || 1, Math.min(num, opt.max_level || 20));
    onOptionsChange([{ ...opt, level: clamped }]);
  };

  // No option selected yet, or editing name — show search
  if (!opt || editingName) {
    return (
      <div className="p-3">
        <ConfigSearchInput
          items={items}
          getLabel={(item) => item.option_name}
          onSelect={handleSelect}
          onCancel={() => setEditingName(false)}
          placeholder={t('sections.echostone.searchOption')}
          showAllOnEmpty
        />
      </div>
    );
  }

  // Option selected — show name + level
  return (
    <div className={cardItem}>
      <div className={`${groupRow} mb-1`}>
        <div className={flexCenter}>
          <span className="text-sm font-medium text-cyan-300">{opt.option_name}</span>
          <button type="button" onClick={() => setEditingName(true)} className={iconBtnEdit} title={t('sections.reforge.correct')}>
            <Pencil className="w-3 h-3" />
          </button>
        </div>
        {editingLevel ? (
          <input
            type="text"
            autoFocus
            value={levelDraft}
            onChange={(e) => setLevelDraft(e.target.value)}
            onBlur={() => commitLevel(levelDraft)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') commitLevel(levelDraft);
              if (e.key === 'Escape') setEditingLevel(false);
            }}
            className={editLevelCyan}
          />
        ) : (
          <LevelBadge
            level={opt.level} maxLevel={opt.max_level} minLevel={opt.min_level}
            className={badgeClickable}
            onClick={() => { setLevelDraft(String(opt.level ?? '')); setEditingLevel(true); }}
            title={t('sections.reforge.clickToEditLevel')}
          >
            Level {opt.level ?? '?'} / {opt.max_level ?? '?'}
          </LevelBadge>
        )}
      </div>
    </div>
  );
};

export default EchostoneSection;
