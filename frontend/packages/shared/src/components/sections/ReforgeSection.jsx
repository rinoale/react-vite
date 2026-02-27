import React, { useState, useMemo } from 'react';
import { Pencil } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ConfigSearchInput from '../ConfigSearchInput';
import { LINE_BULLET } from '../../lib/constants';

const ReforgeOption = ({ opt, optIdx, lineIdx, onLineChange }) => {
  const { t } = useTranslation();
  const [editingName, setEditingName] = useState(false);
  const [editingLevel, setEditingLevel] = useState(false);
  const [levelDraft, setLevelDraft] = useState('');

  const reforgeItems = useMemo(() => window.REFORGES_CONFIG || [], []);

  const commitLevel = (value) => {
    setEditingLevel(false);
    if (value === '' || value === String(opt.level)) return;
    const numLevel = parseInt(value, 10);
    if (isNaN(numLevel)) return;
    const newText = `${LINE_BULLET}${opt.name} (${numLevel}/${opt.max_level} 레벨)`;
    onLineChange(lineIdx, newText, (sec) => {
      if (sec.options) {
        const opts = [...sec.options];
        opts[optIdx] = { ...opts[optIdx], level: numLevel, option_level: numLevel };
        sec.options = opts;
      }
    });
  };

  return (
    <div className="bg-gray-900/50 p-2 rounded border border-gray-700">
      {editingName ? (
        <ConfigSearchInput
          items={reforgeItems}
          getLabel={(item) => typeof item === 'string' ? item : item.option_name}
          onSelect={(item) => {
            const name = typeof item === 'string' ? item : item.option_name;
            const reforgeOptionId = typeof item === 'string' ? null : item.id;
            const newText = opt.level != null
              ? `${LINE_BULLET}${name} (${opt.level}/${opt.max_level} 레벨)`
              : `${LINE_BULLET}${name}`;
            onLineChange(lineIdx, newText, (sec) => {
              if (sec.options) {
                const opts = [...sec.options];
                opts[optIdx] = { ...opts[optIdx], name, option_name: name, reforge_option_id: reforgeOptionId };
                sec.options = opts;
              }
            });
            setEditingName(false);
          }}
          onCancel={() => setEditingName(false)}
          placeholder={t('sections.reforge.searchReforgeOption')}
        />
      ) : (
        <div className="group flex justify-between items-center mb-1">
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium text-cyan-300">{opt.name}</span>
            <button
              onClick={() => setEditingName(true)}
              className="p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-cyan-400 transition-opacity"
              title={t('sections.reforge.correct')}
            >
              <Pencil className="w-3 h-3" />
            </button>
          </div>
          {opt.level != null && (
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
                className="w-16 text-xs text-cyan-300 bg-gray-900 border border-cyan-500 rounded px-1 py-0.5 text-center outline-none"
              />
            ) : (
              <span
                className="text-xs bg-cyan-900/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-700/50 cursor-pointer hover:border-cyan-500"
                onClick={() => { setLevelDraft(String(opt.level)); setEditingLevel(true); }}
                title={t('sections.reforge.clickToEditLevel')}
              >
                Level {opt.level} / {opt.max_level}
              </span>
            )
          )}
        </div>
      )}
      {!editingName && opt.effect && <p className="text-xs text-gray-400">ㄴ {opt.effect}</p>}
    </div>
  );
};

const ReforgeSection = ({ options, lines, onLineChange }) => {
  if (options?.length > 0) {
    return (
      <div className="space-y-3">
        {options.map((opt, idx) => {
          // Resolve section-local line index from option's global_index
          const lineIdx = opt.global_index != null
            ? lines?.findIndex(l => l.global_index === opt.global_index) ?? -1
            : -1;
          return (
            <ReforgeOption
              key={idx}
              opt={opt}
              optIdx={idx}
              lineIdx={lineIdx}
              onLineChange={onLineChange}
            />
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {lines?.map((line, idx) => (
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
};

export default ReforgeSection;
