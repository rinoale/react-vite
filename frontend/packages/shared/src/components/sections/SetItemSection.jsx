import React, { useState, useMemo } from 'react';
import { Pencil, Plus, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ConfigSearchInput from '../ConfigSearchInput';

const MAX_LEVEL = 10;

const SET_NAMES = [
  '골드 스트라이크', '공격 속도', '낚시', '다운 어택', '돌진',
  '라데카 이동 속도', '라이프 드레인', '매그넘 샷', '반신화', '배쉬',
  '블랙 스미스', '서포트 샷', '스매시', '아이스 볼트', '야금술',
  '워터 캐논', '윈드밀', '제련', '최대 대미지', '충격 흡수',
  '크리티컬 대미지', '파이어 볼트', '플레이머', '힐링',
];

/** Trim trailing 강화/증가 from set_name for display. */
const trimSuffix = (name) => name?.replace(/\s*(강화|증가)$/, '') || '';

const SetEffect = ({ eff, idx, onLineChange, onRemove }) => {
  const { t } = useTranslation();
  const [editingName, setEditingName] = useState(false);
  const [editingLevel, setEditingLevel] = useState(false);
  const [levelDraft, setLevelDraft] = useState('');

  const displayName = trimSuffix(eff.set_name);

  const commitLevel = (value) => {
    setEditingLevel(false);
    if (value === '' || value === String(eff.set_level)) return;
    const n = parseInt(value, 10);
    if (isNaN(n)) return;
    const clamped = Math.max(1, Math.min(MAX_LEVEL, n));
    onLineChange(-1, '', (sec) => {
      if (sec.set_effects) {
        const effects = [...sec.set_effects];
        effects[idx] = { ...effects[idx], set_level: clamped };
        sec.set_effects = effects;
      }
    });
  };

  return (
    <div className="bg-gray-900/50 p-2 rounded border border-gray-700">
      {editingName ? (
        <ConfigSearchInput
          items={SET_NAMES}
          getLabel={(item) => item}
          onSelect={(item) => {
            const suffix = eff.set_name?.endsWith('증가') ? ' 증가' : ' 강화';
            const newName = item + suffix;
            onLineChange(-1, '', (sec) => {
              if (sec.set_effects) {
                const effects = [...sec.set_effects];
                effects[idx] = { ...effects[idx], set_name: newName };
                sec.set_effects = effects;
              }
            });
            setEditingName(false);
          }}
          onCancel={() => setEditingName(false)}
          placeholder={t('sections.set_item.searchSetName')}
        />
      ) : (
        <div className="group flex justify-between items-center">
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium text-cyan-300">{displayName}</span>
            <button
              onClick={() => setEditingName(true)}
              className="p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-cyan-400 transition-opacity"
              title={t('sections.set_item.correct')}
            >
              <Pencil className="w-3 h-3" />
            </button>
            <button
              onClick={() => onRemove(idx)}
              className="p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity"
              title={t('sections.set_item.remove')}
            >
              <X className="w-3 h-3" />
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
              className="w-16 text-xs text-cyan-300 bg-gray-900 border border-cyan-500 rounded px-1 py-0.5 text-center outline-none"
            />
          ) : (
            <span
              className="text-xs px-2 py-0.5 rounded border cursor-pointer bg-cyan-900/50 text-cyan-300 border-cyan-700/50 hover:border-cyan-500"
              onClick={() => { setLevelDraft(String(eff.set_level ?? '')); setEditingLevel(true); }}
              title={t('sections.set_item.clickToEditLevel')}
            >
              {eff.set_level ?? 0} / {MAX_LEVEL}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

const AddSetEffect = ({ onLineChange, existingCount }) => {
  const { t } = useTranslation();
  const [searching, setSearching] = useState(false);

  if (searching) {
    return (
      <div className="p-3">
        <ConfigSearchInput
          items={SET_NAMES}
          getLabel={(item) => item}
          onSelect={(item) => {
            const newEff = {
              set_name: item + ' 강화',
              set_level: 1,
            };
            onLineChange(-1, '', (sec) => {
              sec.set_effects = [...(sec.set_effects || []), newEff];
            });
            setSearching(false);
          }}
          onCancel={() => setSearching(false)}
          placeholder={t('sections.set_item.searchSetName')}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setSearching(true)}
      className="w-full border-2 border-dashed border-gray-700 hover:border-cyan-500 rounded-lg p-3 text-sm text-gray-500 hover:text-cyan-300 transition-colors flex items-center justify-center gap-2"
    >
      <Plus className="w-4 h-4" />
      {t('sections.set_item.addEffect')}
    </button>
  );
};

const SetItemSection = ({ lines, set_effects, onLineChange }) => {
  const handleRemove = (effIdx) => {
    onLineChange(-1, '', (sec) => {
      if (sec.set_effects) {
        sec.set_effects = sec.set_effects.filter((_, i) => i !== effIdx);
      }
    });
  };

  if (set_effects?.length > 0) {
    return (
      <div className="space-y-3">
        {set_effects.map((eff, idx) => (
          <SetEffect key={idx} eff={eff} idx={idx} onLineChange={onLineChange} onRemove={handleRemove} />
        ))}
        <AddSetEffect onLineChange={onLineChange} existingCount={set_effects.length} />
      </div>
    );
  }

  if (lines?.length > 0) {
    return (
      <div className="space-y-1">
        {lines.filter(l => !l.is_header).map((line, idx) => (
          <input
            key={idx}
            type="text"
            value={line.text}
            onChange={(e) => onLineChange(idx, e.target.value)}
            className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 focus:ring-1 focus:ring-orange-500 outline-none"
          />
        ))}
      </div>
    );
  }

  return <AddSetEffect onLineChange={onLineChange} existingCount={0} />;
};

export default SetItemSection;
