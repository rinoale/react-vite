import React, { useState, useCallback, useMemo } from 'react';
import { X, ChevronUp } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  chipFilterContent,
  filterRow, filterOpBtn, filterBadgeRow,
  filterValueInput, filterRemoveBtn, filterAddSelect,
  filterBadgeSm, filterBadgePurple,
  reforgeNameLabel,
  filterEffectRow, filterEffectLabel, filterEffectRange,
  filterOpBtnSm, filterLevelInput, getFilterLevelColor,
  filterItemCol, filterChevronPurple,
  filterTypeBtn, filterTypeBtnActive,
} from '../styles/index.js';
import {
  FILTER_OPTIONS, FILTER_MAP, ERG_GRADES, SPECIAL_UPGRADE_TYPES,
  OPS, OP_SYMBOLS,
} from '../lib/filterConstants.js';
import ConfigSearchInput from './ConfigSearchInput.jsx';

const MAX_REFORGES = 3;
const DEFAULT_REFORGE_MAX = 20;

/* ── Attr Filter (always expanded) ── */

const AttrFilterItem = ({ filter, index, onUpdate, onRemove, t }) => {
  const opt = FILTER_MAP[filter.key];

  const handleOp = useCallback(() => {
    const next = OPS[(OPS.indexOf(filter.op) + 1) % OPS.length];
    onUpdate(index, { op: next });
  }, [filter.op, index, onUpdate]);
  const handleValue = useCallback((e) => {
    const v = e.target.value.replace(/[^0-9]/g, '');
    onUpdate(index, { value: v });
  }, [index, onUpdate]);
  const handleRemove = useCallback(() => onRemove(index), [index, onRemove]);

  return (
    <div className={filterRow}>
      <span className={reforgeNameLabel}>{t(opt.i18nKey)}</span>
      <button type="button" onClick={handleOp} className={filterOpBtn}>
        <span key={filter.op} className="inline-block animate-op-spin">
          {OP_SYMBOLS[filter.op]}
        </span>
      </button>
      <input
        type="text"
        inputMode="numeric"
        value={filter.value}
        onChange={handleValue}
        placeholder=""
        className={filterValueInput}
      />
      <button type="button" onClick={handleRemove} className={filterRemoveBtn}>
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};

/* ── Erg Filter (always expanded, grade buttons + level) ── */

const ErgFilterItem = ({ filter, index, onUpdate, onRemove }) => {
  const handleGrade = useCallback((grade) => () => onUpdate(index, { grade }), [index, onUpdate]);
  const handleOp = useCallback(() => {
    const next = OPS[(OPS.indexOf(filter.op) + 1) % OPS.length];
    onUpdate(index, { op: next });
  }, [filter.op, index, onUpdate]);
  const handleValue = useCallback((e) => {
    const v = e.target.value.replace(/[^0-9]/g, '');
    onUpdate(index, { value: v });
  }, [index, onUpdate]);
  const handleRemove = useCallback(() => onRemove(index), [index, onRemove]);

  return (
    <div className={filterRow}>
      {ERG_GRADES.map((g) => (
        <button
          key={g}
          type="button"
          onClick={handleGrade(g)}
          className={filter.grade === g ? filterTypeBtnActive : filterTypeBtn}
        >
          {g}
        </button>
      ))}
      <button type="button" onClick={handleOp} className={filterOpBtn}>
        <span key={filter.op} className="inline-block animate-op-spin">
          {OP_SYMBOLS[filter.op]}
        </span>
      </button>
      <input
        type="text"
        inputMode="numeric"
        value={filter.value}
        onChange={handleValue}
        placeholder=""
        className={filterValueInput}
      />
      <button type="button" onClick={handleRemove} className={filterRemoveBtn}>
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};

/* ── Special Upgrade Filter (always expanded, type buttons + level) ── */

const SpecialUpgradeFilterItem = ({ filter, index, onUpdate, onRemove, t }) => {
  const handleType = useCallback((type) => () => onUpdate(index, { type }), [index, onUpdate]);
  const handleOp = useCallback(() => {
    const next = OPS[(OPS.indexOf(filter.op) + 1) % OPS.length];
    onUpdate(index, { op: next });
  }, [filter.op, index, onUpdate]);
  const handleValue = useCallback((e) => {
    const v = e.target.value.replace(/[^0-9]/g, '');
    onUpdate(index, { value: v });
  }, [index, onUpdate]);
  const handleRemove = useCallback(() => onRemove(index), [index, onRemove]);

  return (
    <div className={filterRow}>
      {SPECIAL_UPGRADE_TYPES.map((tp) => (
        <button
          key={tp}
          type="button"
          onClick={handleType(tp)}
          className={filter.type === tp ? filterTypeBtnActive : filterTypeBtn}
        >
          {t(`marketplace.filter.specialUpgradeType.${tp}`)}
        </button>
      ))}
      <button type="button" onClick={handleOp} className={filterOpBtn}>
        <span key={filter.op} className="inline-block animate-op-spin">
          {OP_SYMBOLS[filter.op]}
        </span>
      </button>
      <input
        type="text"
        inputMode="numeric"
        value={filter.value}
        onChange={handleValue}
        placeholder=""
        className={filterValueInput}
      />
      <button type="button" onClick={handleRemove} className={filterRemoveBtn}>
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};

/* ── Expandable Reforge Filter (folded on add) ── */

const ReforgeFilterItem = ({ filter, index, onUpdate, onRemove }) => {
  const hasLevel = filter.level !== '' && filter.level != null;
  const [isOpen, setIsOpen] = useState(false);
  const maxLvl = filter.max_level || DEFAULT_REFORGE_MAX;
  const levelColor = getFilterLevelColor(filter.level, maxLvl);

  const handleOp = useCallback(() => {
    const next = OPS[(OPS.indexOf(filter.op) + 1) % OPS.length];
    onUpdate(index, { op: next });
  }, [filter.op, index, onUpdate]);
  const handleLevel = useCallback((e) => {
    const v = e.target.value.replace(/[^0-9]/g, '');
    onUpdate(index, { level: v });
  }, [index, onUpdate]);
  const handleRemove = useCallback((e) => { e.stopPropagation(); onRemove(index); }, [index, onRemove]);
  const toggle = useCallback(() => setIsOpen((v) => !v), []);

  if (!isOpen) {
    return (
      <div className={filterBadgeRow} onClick={toggle}>
        <span className={filterBadgeSm}>
          {filter.option_name.slice(0, 6)}{hasLevel ? `${OP_SYMBOLS[filter.op]}${filter.level}` : ''}
        </span>
        <button type="button" onClick={handleRemove} className={filterRemoveBtn}>
          <X className="w-3 h-3" />
        </button>
      </div>
    );
  }

  return (
    <div className={filterRow}>
      <span className={reforgeNameLabel} title={filter.option_name}>
        {filter.option_name}
      </span>
      <button type="button" onClick={handleOp} className={filterOpBtn}>
        <span key={filter.op} className="inline-block animate-op-spin">
          {OP_SYMBOLS[filter.op]}
        </span>
      </button>
      <input
        type="text"
        inputMode="numeric"
        value={filter.level}
        onChange={handleLevel}
        placeholder=""
        className={`${filterLevelInput} ${levelColor}`}
      />
      <button type="button" onClick={toggle} className={filterRemoveBtn}>
        <ChevronUp className="w-3 h-3" />
      </button>
      <button type="button" onClick={handleRemove} className={filterRemoveBtn}>
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};

/* ── Enchant Effect Row ── */

const EnchantEffectRow = ({ effect, enchantIdx, effectIdx, onUpdateEffect }) => {
  const levelColor = getFilterLevelColor(effect.value, effect.max, effect.min);

  const handleOp = useCallback(() => {
    const next = OPS[(OPS.indexOf(effect.op) + 1) % OPS.length];
    onUpdateEffect(enchantIdx, effectIdx, { op: next });
  }, [effect.op, enchantIdx, effectIdx, onUpdateEffect]);
  const handleValue = useCallback((e) => {
    const v = e.target.value.replace(/[^0-9]/g, '');
    onUpdateEffect(enchantIdx, effectIdx, { value: v });
  }, [enchantIdx, effectIdx, onUpdateEffect]);

  return (
    <div className={filterEffectRow}>
      <span className={filterEffectLabel} title={effect.option_name}>
        {effect.option_name}
      </span>
      <button type="button" onClick={handleOp} className={filterOpBtnSm}>
        <span key={effect.op} className="inline-block animate-op-spin">
          {OP_SYMBOLS[effect.op]}
        </span>
      </button>
      <input
        type="text"
        inputMode="numeric"
        value={effect.value}
        onChange={handleValue}
        placeholder=""
        className={`${filterLevelInput} ${levelColor}`}
      />
      {effect.min != null && effect.max != null && (
        <span className={filterEffectRange}>({effect.min}~{effect.max})</span>
      )}
    </div>
  );
};

/* ── Expandable Enchant Filter (folded on add) ── */

const EnchantFilterItem = ({ filter, index, onRemove, onUpdateEffect }) => {
  const rangedEffects = filter.effectFilters || [];
  const hasEffects = rangedEffects.length > 0;
  const [isOpen, setIsOpen] = useState(false);
  const handleRemove = useCallback((e) => { e.stopPropagation(); onRemove(index); }, [index, onRemove]);
  const toggle = useCallback(() => setIsOpen((v) => !v), []);

  if (!isOpen) {
    return (
      <div className={filterBadgeRow} onClick={hasEffects ? toggle : undefined}>
        <span className={filterBadgePurple}>
          {filter.name}
        </span>
        <button type="button" onClick={handleRemove} className={filterRemoveBtn}>
          <X className="w-3 h-3" />
        </button>
      </div>
    );
  }

  return (
    <div className={filterItemCol}>
      {/* enchant-header */}
      <div className={filterBadgeRow} onClick={toggle}>
        <span className={filterBadgePurple}>
          {filter.name}
        </span>
        {hasEffects && <ChevronUp className={filterChevronPurple} />}
        <span className="flex-1" />
        <button type="button" onClick={handleRemove} className={filterRemoveBtn}>
          <X className="w-3 h-3" />
        </button>
      </div>
      {/* enchant-effects */}
      {rangedEffects.map((effect, effectIdx) => (
        <EnchantEffectRow
          key={effectIdx}
          effect={effect}
          enchantIdx={index}
          effectIdx={effectIdx}
          onUpdateEffect={onUpdateEffect}
        />
      ))}
    </div>
  );
};

/* ── Attr filter item dispatcher ── */

const AttrFilterDispatch = ({ filter, index, onUpdate, onRemove, t }) => {
  const opt = FILTER_MAP[filter.key];
  if (!opt) return null;
  if (opt.kind === 'erg') return <ErgFilterItem filter={filter} index={index} onUpdate={onUpdate} onRemove={onRemove} />;
  if (opt.kind === 'special_upgrade') return <SpecialUpgradeFilterItem filter={filter} index={index} onUpdate={onUpdate} onRemove={onRemove} t={t} />;
  return <AttrFilterItem filter={filter} index={index} onUpdate={onUpdate} onRemove={onRemove} t={t} />;
};

/* ── Main panel ── */

const ChipFilterPanel = ({
  isExpanded,
  attrFilters, onAddAttrFilter, onUpdateAttrFilter, onRemoveAttrFilter,
  reforgeFilters, onAddReforgeFilter, onUpdateReforgeFilter, onRemoveReforgeFilter,
  enchantFilters, onAddEnchantFilter, onRemoveEnchantFilter, onUpdateEnchantEffect,
}) => {
  const { t } = useTranslation();
  // null = button, 'pick' = unified list, 'reforge' = reforge search, 'enchant' = enchant search
  const [addMode, setAddMode] = useState(null);

  const reforgeItems = useMemo(() => window.REFORGES_CONFIG || [], []);
  const allEnchantItems = useMemo(() => window.ENCHANTS_CONFIG || [], []);

  const usedKeys = useMemo(() => new Set(attrFilters.map((f) => f.key)), [attrFilters]);
  const reforgesFull = reforgeFilters.length >= MAX_REFORGES;
  const hasPrefix = enchantFilters.some((f) => f.slot === 0);
  const hasSuffix = enchantFilters.some((f) => f.slot === 1);
  const enchantsFull = hasPrefix && hasSuffix;

  // Unified items list for the "Add Filter" picker
  // Order: enchant → reforge → erg → SU → rest
  const unifiedItems = useMemo(() => {
    const items = [];
    if (!enchantsFull) items.push({ key: '_enchant', i18nKey: 'marketplace.filter.addEnchant', _action: 'enchant' });
    if (!reforgesFull) items.push({ key: '_reforge', i18nKey: 'marketplace.filter.addReforge', _action: 'reforge' });
    for (const opt of FILTER_OPTIONS) {
      if (!usedKeys.has(opt.key)) items.push({ ...opt, _action: 'attr' });
    }
    return items;
  }, [usedKeys, reforgesFull, enchantsFull]);

  const availableEnchants = useMemo(
    () => allEnchantItems.filter((e) => (e.slot === 0 && !hasPrefix) || (e.slot === 1 && !hasSuffix)),
    [allEnchantItems, hasPrefix, hasSuffix],
  );

  const handleSelectReforge = useCallback((item) => {
    onAddReforgeFilter({ option_name: item.option_name, op: 'gte', level: '', max_level: item.max_level || DEFAULT_REFORGE_MAX });
    setAddMode(null);
  }, [onAddReforgeFilter]);

  const handleSelectEnchant = useCallback((item) => {
    const rangedEffects = (item.effects || [])
      .filter((e) => e.ranged)
      .map((e) => ({
        enchant_effect_id: e.enchant_effect_id,
        option_name: e.option_name,
        op: 'gte',
        value: '',
        min: e.min,
        max: e.max,
      }));
    onAddEnchantFilter({ name: item.name, slot: item.slot, effectFilters: rangedEffects });
    setAddMode(null);
  }, [onAddEnchantFilter]);

  const handlePickSelect = useCallback((e) => {
    const key = e.target.value;
    if (!key) return;
    const item = unifiedItems.find((i) => i.key === key);
    if (!item) return;
    if (item._action === 'reforge') { setAddMode('reforge'); }
    else if (item._action === 'enchant') { setAddMode('enchant'); }
    else { onAddAttrFilter(item.key); setAddMode(null); }
  }, [unifiedItems, onAddAttrFilter]);

  const getReforgeLabel = useCallback((item) => item.option_name, []);
  const getEnchantLabel = useCallback((item) => {
    const slot = item.slot === 0 ? t('marketplace.filter.prefix') : t('marketplace.filter.suffix');
    return `[${slot}] ${item.name}`;
  }, [t]);
  const cancelAdd = useCallback(() => setAddMode(null), []);

  const nothingToAdd = unifiedItems.length === 0;

  return (
    <div className={`${chipFilterContent} ${isExpanded ? 'opacity-100' : 'opacity-0 -translate-y-1'}`}>
      {/* attr / erg / special_upgrade filters */}
      {attrFilters.map((filter, idx) => (
        <AttrFilterDispatch
          key={`attr-${filter.key}`}
          filter={filter}
          index={idx}
          onUpdate={onUpdateAttrFilter}
          onRemove={onRemoveAttrFilter}
          t={t}
        />
      ))}
      {/* reforge filters */}
      {reforgeFilters.map((filter, idx) => (
        <ReforgeFilterItem
          key={`reforge-${idx}`}
          filter={filter}
          index={idx}
          onUpdate={onUpdateReforgeFilter}
          onRemove={onRemoveReforgeFilter}
        />
      ))}
      {/* enchant filters */}
      {enchantFilters.map((filter, idx) => (
        <EnchantFilterItem
          key={`enchant-${idx}`}
          filter={filter}
          index={idx}
          onRemove={onRemoveEnchantFilter}
          onUpdateEffect={onUpdateEnchantEffect}
        />
      ))}
      {/* unified add-filter */}
      {!nothingToAdd && (
        <div className={filterRow}>
          {addMode === null && (
            <select value="" onChange={handlePickSelect} className={filterAddSelect}>
              <option value="" disabled>+ {t('marketplace.filter.addFilter')}</option>
              {unifiedItems.map((item) => (
                <option key={item.key} value={item.key}>{t(item.i18nKey)}</option>
              ))}
            </select>
          )}
          {addMode === 'reforge' && (
            <ConfigSearchInput
              items={reforgeItems}
              getLabel={getReforgeLabel}
              onSelect={handleSelectReforge}
              onCancel={cancelAdd}
              placeholder={t('marketplace.filter.searchReforge')}
            />
          )}
          {addMode === 'enchant' && (
            <ConfigSearchInput
              items={availableEnchants}
              getLabel={getEnchantLabel}
              onSelect={handleSelectEnchant}
              onCancel={cancelAdd}
              placeholder={t('marketplace.filter.searchEnchant')}
            />
          )}
        </div>
      )}
      {/* spacer for dropdown overflow */}
      {addMode != null && <div className="h-32" />}
    </div>
  );
};

export default ChipFilterPanel;
