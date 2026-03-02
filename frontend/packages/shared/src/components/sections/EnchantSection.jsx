import React, { useState, useMemo } from 'react';
import { Pencil, Plus, AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ConfigSearchInput from '../ConfigSearchInput';
import { LINE_BULLET } from '../../lib/constants';

/** Find enchant config entry matching name + slot */
function findEnchantConfig(name, slotInt) {
  return (window.ENCHANTS_CONFIG || []).find(
    e => e.name === name && e.slot === slotInt
  );
}

/** Extract first number from text */
function extractNumber(text) {
  const m = text && text.match(/(\d+(?:\.\d+)?)/);
  return m ? (m[1].includes('.') ? parseFloat(m[1]) : parseInt(m[1], 10)) : null;
}

/** Build effect display text from config entry and rolled value.
 *  abbreviated=true  → "option_name level suffix"
 *  abbreviated=false → full config text with number/range replaced by rolled value */
function buildEffectText(ce, level, abbreviated) {
  if (abbreviated || !ce.text || !ce.option_name) {
    return ce.option_name + ' ' + level + (ce.suffix || '');
  }
  // Full form: find option_name in ce.text, replace the number after it
  const nameIdx = ce.text.indexOf(ce.option_name);
  if (nameIdx < 0) return ce.option_name + ' ' + level + (ce.suffix || '');
  const prefix = ce.text.slice(0, nameIdx);
  const afterName = ce.text.slice(nameIdx + ce.option_name.length);
  const replaced = afterName.replace(/\s*\d+(?:\.\d+)?(?:\s*~\s*\d+(?:\.\d+)?)?/, ' ' + level);
  return prefix + ce.option_name + replaced;
}

/** Rebuild effects from new config, pulling rolled values from OCR lines.
 *  Each effect owns its line reference via line_index. */
function rebuildEffects(newConfig, sectionLines, abbreviated) {
  if (!newConfig?.effects) return [];
  // Collect non-header OCR lines
  const ocrLines = (sectionLines || []).filter(l =>
    l.text && !l.text.startsWith('[접두]') && !l.text.startsWith('[접미]')
  );
  const usedOcr = new Set();
  return newConfig.effects.map(ce => {
    const eff = { text: ce.text, option_name: ce.option_name || null, option_level: null, line_index: null };
    if (!ce.option_name) return eff;
    // Find OCR line containing this option_name to extract rolled value
    const ocrIdx = ocrLines.findIndex(
      (l, i) => !usedOcr.has(i) && l.text.includes(ce.option_name)
    );
    if (ocrIdx >= 0) {
      usedOcr.add(ocrIdx);
      const line = ocrLines[ocrIdx];
      eff.line_index = line.line_index;
      const after = line.text.slice(line.text.indexOf(ce.option_name) + ce.option_name.length);
      const rolled = extractNumber(after);
      if (rolled != null) {
        eff.option_level = rolled;
        eff.text = buildEffectText(ce, rolled, abbreviated);
      }
    }
    return eff;
  });
}

const EffectRow = ({ eff, lineIdx, onLineChange, configEffects, abbreviated }) => {
  const { t } = useTranslation();
  const [editingName, setEditingName] = useState(false);
  const [editingLevel, setEditingLevel] = useState(false);
  const [levelDraft, setLevelDraft] = useState('');

  // Find matching config effect — fuzzy: OCR option_name may contain garbled
  // condition text appended after the real effect name, so use includes + longest match
  const matchingConfig = (() => {
    if (!configEffects || !eff.option_name) return null;
    const exact = configEffects.find(ce => ce.option_name === eff.option_name);
    if (exact) return exact;
    return configEffects
      .filter(ce => ce.option_name && eff.option_name.includes(ce.option_name))
      .sort((a, b) => b.option_name.length - a.option_name.length)[0] || null;
  })();
  const isRanged = matchingConfig?.ranged ?? false;
  const rangeMin = matchingConfig?.min ?? null;
  const rangeMax = matchingConfig?.max ?? null;
  const hasRange = rangeMin != null && rangeMax != null;

  const isOutOfRange = hasRange && eff.option_level != null &&
    (eff.option_level < rangeMin || eff.option_level > rangeMax);

  const draftNum = levelDraft !== '' ? (levelDraft.includes('.') ? parseFloat(levelDraft) : parseInt(levelDraft, 10)) : NaN;
  const isDraftOutOfRange = hasRange && !isNaN(draftNum) && (draftNum < rangeMin || draftNum > rangeMax);

  const commitLevel = (value) => {
    setEditingLevel(false);
    if (value === '' || value === String(eff.option_level)) return;
    const numLevel = value.includes('.') ? parseFloat(value) : parseInt(value, 10);
    if (isNaN(numLevel)) return;
    const newEffText = buildEffectText(matchingConfig, numLevel, abbreviated);
    onLineChange(lineIdx, LINE_BULLET + newEffText, null, { option_name: matchingConfig.option_name, option_level: numLevel });
  };

  if (editingName && configEffects && configEffects.length > 0) {
    return (
      <div className="flex items-center gap-1">
        <span className="text-gray-600 mr-1">.</span>
        <ConfigSearchInput
          items={configEffects}
          getLabel={(item) => item.text}
          onSelect={(selected) => {
            const newEffText = buildEffectText(selected, eff.option_level, abbreviated);
            onLineChange(lineIdx, LINE_BULLET + newEffText, null, { option_name: selected.option_name });
            setEditingName(false);
          }}
          onCancel={() => setEditingName(false)}
          placeholder={t('sections.enchant.searchEffect')}
        />
      </div>
    );
  }

  // Safely extract suffix text after option_level
  const levelStr = eff.option_level != null ? String(eff.option_level) : null;
  const suffixText = (() => {
    if (levelStr == null) return '';
    const idx = eff.text.indexOf(levelStr);
    if (idx < 0) return '';
    return eff.text.slice(idx + levelStr.length).trim();
  })();

  return (
    <div className="group flex items-center gap-1 text-xs text-gray-400">
      <span className="text-gray-600 mr-1">.</span>
      {eff.option_name != null ? (
        <>
          <span>{eff.option_name} </span>
          {isRanged && editingLevel ? (
            <span className="inline-flex items-center gap-1">
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
                className={`w-12 text-orange-400 font-bold bg-gray-900 border rounded px-1 text-xs text-center outline-none ${isDraftOutOfRange ? 'border-red-500' : 'border-orange-500'}`}
              />
              {hasRange && <span className="text-[10px] text-gray-600">{rangeMin}~{rangeMax}</span>}
              {isDraftOutOfRange && <AlertTriangle className="w-3 h-3 text-red-500" />}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1">
              <span
                className={isRanged ? 'text-orange-400 font-bold cursor-pointer hover:underline' : ''}
                onClick={isRanged ? () => { setLevelDraft(eff.option_level != null ? String(eff.option_level) : ''); setEditingLevel(true); } : undefined}
                title={isRanged ? t('sections.enchant.clickToEditValue') : undefined}
              >
                {eff.option_level != null ? eff.option_level : (isRanged ? '?' : '')}
              </span>
              {isOutOfRange && <AlertTriangle className="w-3 h-3 text-red-500" title={t('sections.enchant.outOfRange', { min: rangeMin, max: rangeMax })} />}
            </span>
          )}
          {suffixText && <span> {suffixText}</span>}
        </>
      ) : (
        <span>{eff.text}</span>
      )}
      {isRanged && (
        <button
          onClick={() => setEditingName(true)}
          className="ml-auto p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-orange-400 transition-opacity"
          title={t('sections.enchant.correctEffect')}
        >
          <Pencil className="w-3 h-3" />
        </button>
      )}
    </div>
  );
};

const EnchantSlot = ({ slot, slotLabel, headerLineIdx, lines, onLineChange, abbreviated }) => {
  const { t } = useTranslation();
  const [editingHeader, setEditingHeader] = useState(false);

  const slotInt = slotLabel === 'Prefix' ? 0 : 1;
  const enchantItems = useMemo(
    () => (window.ENCHANTS_CONFIG || []).filter(e => e.slot === slotInt),
    [slotInt]
  );

  // Get config entry for the currently identified enchant
  const enchantConfig = useMemo(() => {
    if (!slot) return null;
    return findEnchantConfig(slot.name, slotInt);
  }, [slot, slotInt]);

  const configEffects = enchantConfig?.effects || null;

  if (!slot) return null;

  return (
    <div className="bg-gray-900/50 p-3 rounded border border-gray-700">
      <div className="flex justify-between items-center mb-2">
        {editingHeader ? (
          <ConfigSearchInput
            items={enchantItems}
            getLabel={(item) => `${item.name} (랭크 ${item.rank_label})`}
            onSelect={(item) => {
              const slotKor = item.slot === 0 ? '접두' : '접미';
              const slotKey = slotLabel === 'Prefix' ? 'prefix' : 'suffix';
              const newText = `[${slotKor}] ${item.name} (랭크 ${item.rank_label})`;
              onLineChange(headerLineIdx, newText, (sec) => {
                const newEffects = rebuildEffects(item, sec.lines, abbreviated);
                sec[slotKey] = { ...sec[slotKey], name: item.name, rank: item.rank_label, text: newText, effects: newEffects };
              });
              setEditingHeader(false);
            }}
            onCancel={() => setEditingHeader(false)}
            placeholder={t('sections.enchant.searchEnchant')}
          />
        ) : (
          <div className="group flex items-center gap-1">
            <span className="text-sm font-medium text-purple-300">{slot.name}</span>
            <button
              onClick={() => setEditingHeader(true)}
              className="p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-purple-400 transition-opacity"
              title={t('sections.enchant.correctEnchant')}
            >
              <Pencil className="w-3 h-3" />
            </button>
          </div>
        )}
        <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded border border-purple-700/50 shrink-0 ml-2">
          {slotLabel} · Rank {slot.rank}
        </span>
      </div>
      <div className="space-y-1.5 pl-3 border-l border-purple-900/30">
        {slot.effects.map((eff, i) => {
          // Resolve section-local line index from effect's line_index
          const lineIdx = eff.line_index != null
            ? lines?.findIndex(l => l.line_index === eff.line_index) ?? -1
            : -1;
          const handleEffectChange = (li, newText, extraUpdate, effectMeta) => {
            const sk = slotLabel === 'Prefix' ? 'prefix' : 'suffix';
            const effText = newText.startsWith(LINE_BULLET) ? newText.slice(LINE_BULLET.length) : newText;
            onLineChange(li, newText, (sec) => {
              if (sec[sk]) {
                const effs = [...sec[sk].effects];
                effs[i] = { ...effs[i], text: effText, ...effectMeta };
                sec[sk] = { ...sec[sk], effects: effs };
              }
              if (extraUpdate) extraUpdate(sec);
            });
          };
          return (
            <EffectRow
              key={i}
              eff={eff}
              lineIdx={lineIdx}
              onLineChange={handleEffectChange}
              configEffects={configEffects}
              abbreviated={abbreviated}
            />
          );
        })}
      </div>
    </div>
  );
};

const FallbackLines = ({ slotLines, onLineChange }) => (
  <div className="space-y-1">
    {slotLines.map((line) => (
      <input
        key={line.lineIdx}
        type="text"
        value={line.text}
        onChange={(e) => onLineChange(line.lineIdx, e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 focus:ring-1 focus:ring-orange-500 outline-none"
      />
    ))}
  </div>
);

const AddEnchantSlot = ({ slotLabel, onLineChange }) => {
  const { t } = useTranslation();
  const [searching, setSearching] = useState(false);
  const slotInt = slotLabel === 'Prefix' ? 0 : 1;
  const enchantItems = useMemo(
    () => (window.ENCHANTS_CONFIG || []).filter(e => e.slot === slotInt),
    [slotInt]
  );
  const i18nKey = slotLabel === 'Prefix' ? 'sections.enchant.addPrefix' : 'sections.enchant.addSuffix';
  const slotKey = slotLabel === 'Prefix' ? 'prefix' : 'suffix';

  if (searching) {
    return (
      <div className="p-3">
        <ConfigSearchInput
          items={enchantItems}
          getLabel={(item) => `${item.name} (랭크 ${item.rank_label})`}
          onSelect={(item) => {
            const slotKor = item.slot === 0 ? '접두' : '접미';
            const headerText = `[${slotKor}] ${item.name} (랭크 ${item.rank_label})`;
            const effects = (item.effects || []).map(e => ({
              text: e.text,
              option_name: e.option_name || null,
              option_level: null,
              line_index: null,
            }));
            onLineChange(-1, '', (sec) => {
              sec[slotKey] = { name: item.name, rank: item.rank_label, text: headerText, effects };
            });
            setSearching(false);
          }}
          onCancel={() => setSearching(false)}
          placeholder={t('sections.enchant.searchEnchant')}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setSearching(true)}
      className="w-full border-2 border-dashed border-gray-700 hover:border-purple-500 rounded-lg p-3 text-sm text-gray-500 hover:text-purple-300 transition-colors flex items-center justify-center gap-2"
    >
      <Plus className="w-4 h-4" />
      {t(i18nKey)}
    </button>
  );
};

const EnchantSection = ({ prefix, suffix, lines, onLineChange, abbreviated = true }) => {
  const { groups, headerIndices } = useMemo(() => {
    if (!lines) return {
      groups: { prefix: [], suffix: [], unassigned: [] },
      headerIndices: { prefix: null, suffix: null }
    };

    let currentSlot = null;
    const grp = { prefix: [], suffix: [], unassigned: [] };
    const hdrIdx = { prefix: null, suffix: null };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const text = line.text || '';
      if (text.startsWith('[접두]')) {
        currentSlot = 'prefix';
        hdrIdx.prefix = i;
      } else if (text.startsWith('[접미]')) {
        currentSlot = 'suffix';
        hdrIdx.suffix = i;
      }
      grp[currentSlot || 'unassigned'].push({ ...line, lineIdx: i });
    }

    return { groups: grp, headerIndices: hdrIdx };
  }, [lines]);

  return (
    <div className="space-y-3">
      {prefix ? (
        <EnchantSlot
          slot={prefix}
          slotLabel="Prefix"
          headerLineIdx={headerIndices.prefix}
          lines={lines}
          onLineChange={onLineChange}
          abbreviated={abbreviated}
        />
      ) : groups.prefix.length > 0 ? (
        <FallbackLines slotLines={groups.prefix} onLineChange={onLineChange} />
      ) : (
        <AddEnchantSlot slotLabel="Prefix" onLineChange={onLineChange} />
      )}
      {suffix ? (
        <EnchantSlot
          slot={suffix}
          slotLabel="Suffix"
          headerLineIdx={headerIndices.suffix}
          lines={lines}
          onLineChange={onLineChange}
          abbreviated={abbreviated}
        />
      ) : groups.suffix.length > 0 ? (
        <FallbackLines slotLines={groups.suffix} onLineChange={onLineChange} />
      ) : (
        <AddEnchantSlot slotLabel="Suffix" onLineChange={onLineChange} />
      )}
      {groups.unassigned.length > 0 && (
        <FallbackLines slotLines={groups.unassigned} onLineChange={onLineChange} />
      )}
    </div>
  );
};

export default EnchantSection;
