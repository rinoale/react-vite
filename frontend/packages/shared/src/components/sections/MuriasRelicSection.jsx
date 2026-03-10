import React, { useState, useMemo } from 'react';
import { Pencil, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ConfigSearchInput from '../ConfigSearchInput';
import CustomSelect from '../CustomSelect';
import { cardItem, groupRow, flexCenter, iconBtnEdit, editLevelCyan, badgeClickable } from '../../styles';
import LevelBadge from '../LevelBadge';

const MuriasRelicSection = ({ options, onOptionsChange }) => {
  const { t } = useTranslation();
  const [selectedType, setSelectedType] = useState(null);
  const [editingName, setEditingName] = useState(false);
  const [editingLevel, setEditingLevel] = useState(false);
  const [levelDraft, setLevelDraft] = useState('');

  const allItems = useMemo(() => window.MURIAS_RELIC_CONFIG || [], []);
  const types = useMemo(() => [...new Set(allItems.map(i => i.type))].sort(), [allItems]);
  const typeOptions = useMemo(
    () => types.map(ty => ({ value: ty, label: t(`sections.murias_relic.types.${ty}`) })),
    [types, t],
  );

  const opt = options[0] || null;

  const activeType = opt?.murias_type || selectedType;
  const filteredItems = useMemo(
    () => activeType ? allItems.filter(i => i.type === activeType) : [],
    [allItems, activeType],
  );

  const handleSelect = (item) => {
    onOptionsChange([{
      option_name: item.option_name,
      option_id: item.id,
      murias_type: item.type,
      level: item.min_level || 1,
      min_level: item.min_level || 1,
      max_level: item.max_level || 10,
      value_per_level: item.value_per_level ?? null,
      option_unit: item.option_unit ?? '',
    }]);
    setSelectedType(null);
    setEditingName(false);
  };

  const handleCancel = () => {
    setSelectedType(null);
    setEditingName(false);
  };

  const commitLevel = (value) => {
    setEditingLevel(false);
    if (!opt || value === '' || value === String(opt.level)) return;
    const num = parseInt(value, 10);
    if (isNaN(num)) return;
    const clamped = Math.max(opt.min_level || 1, Math.min(num, opt.max_level || 10));
    onOptionsChange([{ ...opt, level: clamped }]);
  };

  // No option selected — show type selector, then options
  if (!opt && !editingName) {
    // Step 2: type selected, show options
    if (selectedType) {
      return (
        <div className="p-3 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300">
              {t(`sections.murias_relic.types.${selectedType}`)}
            </span>
            <button onClick={handleCancel} className="text-gray-500 hover:text-gray-300">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <ConfigSearchInput
            items={filteredItems}
            getLabel={(item) => item.option_name}
            onSelect={handleSelect}
            onCancel={handleCancel}
            placeholder={t('sections.murias_relic.searchOption')}
            showAllOnEmpty
          />
        </div>
      );
    }

    // Step 1: select type
    return (
      <div className="p-3">
        <CustomSelect
          value=""
          onChange={(val) => setSelectedType(val)}
          options={typeOptions}
          placeholder={t('sections.murias_relic.selectType')}
          triggerClassName="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-400 hover:border-gray-600 transition-colors"
        />
      </div>
    );
  }

  // Editing name on existing option — show type-filtered search
  if (editingName) {
    return (
      <div className="p-3 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300">
            {t(`sections.murias_relic.types.${opt.murias_type}`)}
          </span>
          <button onClick={handleCancel} className="text-gray-500 hover:text-gray-300">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
        <ConfigSearchInput
          items={filteredItems}
          getLabel={(item) => item.option_name}
          onSelect={handleSelect}
          onCancel={handleCancel}
          placeholder={t('sections.murias_relic.searchOption')}
          showAllOnEmpty
        />
      </div>
    );
  }

  // Option selected — show computed value text + level badge
  const computedValue = opt.value_per_level != null && opt.level != null
    ? +(opt.value_per_level * opt.level).toFixed(2)
    : null;
  const valueText = computedValue != null
    ? `${opt.option_name} ${computedValue}${opt.option_unit || ''}`
    : opt.option_name;

  return (
    <div className={cardItem}>
      <div className={`${groupRow} mb-1`}>
        <div className={flexCenter}>
          <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300">
            {t(`sections.murias_relic.types.${opt.murias_type}`)}
          </span>
          <span className="text-sm font-medium text-cyan-300">{valueText}</span>
          <button onClick={() => setEditingName(true)} className={iconBtnEdit} title={t('sections.reforge.correct')}>
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

export default MuriasRelicSection;
