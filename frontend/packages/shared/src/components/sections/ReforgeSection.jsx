import React, { useState, useMemo } from 'react';
import { Pencil, Plus, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ConfigSearchInput from '../ConfigSearchInput';
import { cardItem, groupRow, flexCenter, iconBtnEdit, iconBtnRemove, editLevelCyan, badgeClickable, addBtnCyan, inputCompact, getLevelBadge } from '../../styles';
import LevelBadge from '../LevelBadge';

const ReforgeOption = ({ opt, optIdx, lineIdx, onLineChange, onRemove }) => {
  const { t } = useTranslation();
  const [editingName, setEditingName] = useState(false);
  const [editingLevel, setEditingLevel] = useState(false);
  const [levelDraft, setLevelDraft] = useState('');

  const reforgeItems = useMemo(() => window.REFORGES_CONFIG || [], []);
  const cfgEntry = useMemo(() => reforgeItems.find(r => r.option_name === opt.name), [reforgeItems, opt.name]);
  const maxLvl = opt.max_level || cfgEntry?.max_level;
  const hasLevel = !NO_LEVEL_OPTIONS.includes(opt.name);

  const commitLevel = (value) => {
    setEditingLevel(false);
    if (value === '' || value === String(opt.level)) return;
    const numLevel = parseInt(value, 10);
    if (isNaN(numLevel)) return;
    const maxLevel = opt.max_level || cfgEntry?.max_level || 20;
    const newText = `${opt.name} (${numLevel}/${maxLevel} 레벨)`;
    onLineChange(lineIdx, newText, (sec) => {
      if (sec.options) {
        const opts = [...sec.options];
        opts[optIdx] = { ...opts[optIdx], level: numLevel, max_level: maxLevel, option_level: numLevel };
        sec.options = opts;
      }
    });
  };

  return (
    <div className={cardItem}>
      {editingName ? (
        <ConfigSearchInput
          items={reforgeItems}
          getLabel={(item) => typeof item === 'string' ? item : item.option_name}
          onSelect={(item) => {
            const name = typeof item === 'string' ? item : item.option_name;
            const reforgeOptionId = typeof item === 'string' ? null : item.id;
            const hasLevel = !NO_LEVEL_OPTIONS.includes(name);
            const newLevel = hasLevel ? 1 : null;
            const newMaxLevel = hasLevel ? (typeof item === 'string' ? 20 : (item.max_level || 20)) : null;
            const newText = hasLevel
              ? `${name} (${newLevel}/${newMaxLevel} 레벨)`
              : name;
            onLineChange(lineIdx, newText, (sec) => {
              if (sec.options) {
                const opts = [...sec.options];
                opts[optIdx] = { ...opts[optIdx], name, option_name: name, reforge_option_id: reforgeOptionId, level: newLevel, max_level: newMaxLevel, option_level: newLevel };
                sec.options = opts;
              }
            });
            setEditingName(false);
          }}
          onCancel={() => setEditingName(false)}
          placeholder={t('sections.reforge.searchReforgeOption')}
        />
      ) : (
        <div className={`${groupRow} mb-1`}>
          <div className={flexCenter}>
            <span className="text-sm font-medium text-cyan-300">{opt.name}</span>
            <button
              onClick={() => setEditingName(true)}
              className={iconBtnEdit}
              title={t('sections.reforge.correct')}
            >
              <Pencil className="w-3 h-3" />
            </button>
            <button
              onClick={() => onRemove(optIdx)}
              className={iconBtnRemove}
              title={t('sections.reforge.remove')}
            >
              <X className="w-3 h-3" />
            </button>
          </div>
          {hasLevel && (
            editingLevel ? (
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
            ) : opt.level == null ? (
              <span
                className={`${badgeClickable} bg-gray-600 text-gray-300`}
                onClick={() => { setLevelDraft(''); setEditingLevel(true); }}
                title={t('sections.reforge.clickToEditLevel')}
              >
                {t('sections.reforge.setLevel')}
              </span>
            ) : (
              <LevelBadge
                level={opt.level} maxLevel={maxLvl}
                className={badgeClickable}
                onClick={() => { setLevelDraft(String(opt.level)); setEditingLevel(true); }}
                title={t('sections.reforge.clickToEditLevel')}
              >
                Level {opt.level} / {opt.max_level}
              </LevelBadge>
            )
          )}
        </div>
      )}
      {!editingName && opt.effect && <p className="text-xs text-gray-400">ㄴ {opt.effect}</p>}
    </div>
  );
};

const MAX_REFORGE_OPTIONS = 3;
const NO_LEVEL_OPTIONS = ['돌진 인간 및 엘프일 때 방패 없이 사용 가능'];

const AddReforgeOption = ({ onLineChange, existingCount }) => {
  const { t } = useTranslation();
  const [searching, setSearching] = useState(false);
  const reforgeItems = useMemo(() => window.REFORGES_CONFIG || [], []);

  if (existingCount >= MAX_REFORGE_OPTIONS) return null;

  if (searching) {
    return (
      <div className="p-3">
        <ConfigSearchInput
          items={reforgeItems}
          getLabel={(item) => typeof item === 'string' ? item : item.option_name}
          onSelect={(item) => {
            const name = typeof item === 'string' ? item : item.option_name;
            const reforgeOptionId = typeof item === 'string' ? null : item.id;
            const hasLevel = !NO_LEVEL_OPTIONS.includes(name);
            const newOpt = {
              name,
              option_name: name,
              reforge_option_id: reforgeOptionId,
              level: hasLevel ? 1 : null,
              max_level: hasLevel ? 20 : null,
              effect: null,
              line_index: null,
            };
            onLineChange(-1, '', (sec) => {
              sec.options = [...(sec.options || []), newOpt];
            });
            setSearching(false);
          }}
          onCancel={() => setSearching(false)}
          placeholder={t('sections.reforge.searchReforgeOption')}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setSearching(true)}
      className={addBtnCyan}
    >
      <Plus className="w-4 h-4" />
      {t('sections.reforge.addOption')}
    </button>
  );
};

const ReforgeSection = ({ options, lines, onLineChange }) => {
  const handleRemove = (optIdx) => {
    onLineChange(-1, '', (sec) => {
      if (sec.options) {
        sec.options = sec.options.filter((_, i) => i !== optIdx);
      }
    });
  };

  if (options?.length > 0) {
    return (
      <div className="space-y-3">
        {options.map((opt, idx) => {
          // Resolve section-local line index from option's line_index
          const lineIdx = opt.line_index != null
            ? lines?.findIndex(l => l.line_index === opt.line_index) ?? -1
            : -1;
          return (
            <ReforgeOption
              key={idx}
              opt={opt}
              optIdx={idx}
              lineIdx={lineIdx}
              onLineChange={onLineChange}
              onRemove={handleRemove}
            />
          );
        })}
        <AddReforgeOption onLineChange={onLineChange} existingCount={options.length} />
      </div>
    );
  }

  if (lines?.length > 0) {
    return (
      <div className="space-y-1">
        {lines.map((line, idx) => (
          <input
            key={idx}
            type="text"
            value={line.text}
            onChange={(e) => onLineChange(idx, e.target.value)}
            className={inputCompact}
          />
        ))}
      </div>
    );
  }

  return <AddReforgeOption onLineChange={onLineChange} existingCount={0} />;
};

export default ReforgeSection;
