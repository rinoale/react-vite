import React, { useState, useMemo } from 'react';
import { Pencil } from 'lucide-react';
import ConfigSearchInput from '../ConfigSearchInput';

/** Find enchant config entry matching name + slot */
function findEnchantConfig(name, slotInt) {
  return (window.ENCHANTS_CONFIG || []).find(
    e => e.name === name && e.slot === slotInt
  );
}

const EffectRow = ({ eff, lineIdx, lineText, onLineChange, configEffects }) => {
  const [editingName, setEditingName] = useState(false);
  const [editingLevel, setEditingLevel] = useState(false);
  const [levelDraft, setLevelDraft] = useState('');

  // Find matching config effect to get pre-computed suffix and ranged flag
  const matchingConfig = configEffects?.find(ce => ce.option_name === eff.option_name) || null;
  const isRanged = matchingConfig?.ranged ?? false;

  const commitLevel = (value) => {
    setEditingLevel(false);
    if (value === '' || value === String(eff.option_level)) return;
    const numLevel = value.includes('.') ? parseFloat(value) : parseInt(value, 10);
    if (isNaN(numLevel)) return;
    const newEffText = eff.option_name + ' ' + numLevel + matchingConfig.suffix;
    onLineChange(lineIdx, '- ' + newEffText, null, { option_name: eff.option_name, option_level: numLevel });
  };

  if (editingName && configEffects && configEffects.length > 0) {
    return (
      <div className="flex items-center gap-1">
        <span className="text-gray-600 mr-1">-</span>
        <ConfigSearchInput
          items={configEffects}
          getLabel={(item) => item.text}
          onSelect={(selected) => {
            const newEffText = selected.option_name + ' ' + eff.option_level + selected.suffix;
            onLineChange(lineIdx, '- ' + newEffText, null, { option_name: selected.option_name });
            setEditingName(false);
          }}
          onCancel={() => setEditingName(false)}
          placeholder="Search effect..."
        />
      </div>
    );
  }

  return (
    <div className="group flex items-center gap-1 text-xs text-gray-400">
      <span className="text-gray-600 mr-1">-</span>
      {eff.option_name != null ? (
        <>
          <span>{eff.option_name} </span>
          {isRanged && editingLevel ? (
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
              className="w-12 text-orange-400 font-bold bg-gray-900 border border-orange-500 rounded px-1 text-xs text-center outline-none"
            />
          ) : (
            <span
              className={'text-orange-400 font-bold' + (isRanged ? ' cursor-pointer hover:underline' : '')}
              onClick={isRanged ? () => { setLevelDraft(String(eff.option_level)); setEditingLevel(true); } : undefined}
              title={isRanged ? 'Click to edit value' : undefined}
            >
              {eff.option_level}
            </span>
          )}
          {eff.text.slice(eff.text.indexOf(String(eff.option_level)) + String(eff.option_level).length).trim() && (
            <span> {eff.text.slice(eff.text.indexOf(String(eff.option_level)) + String(eff.option_level).length).trim()}</span>
          )}
        </>
      ) : (
        <span>{eff.text}</span>
      )}
      {isRanged && (
        <button
          onClick={() => setEditingName(true)}
          className="ml-auto p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-orange-400 transition-opacity"
          title="Correct effect"
        >
          <Pencil className="w-3 h-3" />
        </button>
      )}
    </div>
  );
};

const EnchantSlot = ({ slot, slotLabel, headerLineIdx, effectLineIndices, lines, onLineChange }) => {
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
                sec[slotKey] = { ...sec[slotKey], name: item.name, rank: item.rank_label, text: newText };
              });
              setEditingHeader(false);
            }}
            onCancel={() => setEditingHeader(false)}
            placeholder="Search enchant..."
          />
        ) : (
          <div className="group flex items-center gap-1">
            <span className="text-sm font-medium text-purple-300">{slot.name}</span>
            <button
              onClick={() => setEditingHeader(true)}
              className="p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-purple-400 transition-opacity"
              title="Correct enchant"
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
          const lineIdx = effectLineIndices[i];
          const lineText = lines?.[lineIdx]?.text || '';
          const handleEffectChange = (li, newText, extraUpdate, effectMeta) => {
            const sk = slotLabel === 'Prefix' ? 'prefix' : 'suffix';
            const effText = newText.startsWith('- ') ? newText.slice(2) : newText;
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
              lineText={lineText}
              onLineChange={handleEffectChange}
              configEffects={configEffects}
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

const EnchantSection = ({ prefix, suffix, lines, onLineChange }) => {
  const { groups, effectIndices, headerIndices } = useMemo(() => {
    if (!lines) return {
      groups: { prefix: [], suffix: [], unassigned: [] },
      effectIndices: { prefix: [], suffix: [] },
      headerIndices: { prefix: null, suffix: null }
    };

    let currentSlot = null;
    const grp = { prefix: [], suffix: [], unassigned: [] };
    const effIdx = { prefix: [], suffix: [] };
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

      if (currentSlot && !text.startsWith('[접두]') && !text.startsWith('[접미]')) {
        effIdx[currentSlot].push(i);
      }
    }

    return { groups: grp, effectIndices: effIdx, headerIndices: hdrIdx };
  }, [lines]);

  return (
    <div className="space-y-3">
      {prefix ? (
        <EnchantSlot
          slot={prefix}
          slotLabel="Prefix"
          headerLineIdx={headerIndices.prefix}
          effectLineIndices={effectIndices.prefix}
          lines={lines}
          onLineChange={onLineChange}
        />
      ) : groups.prefix.length > 0 ? (
        <FallbackLines slotLines={groups.prefix} onLineChange={onLineChange} />
      ) : null}
      {suffix ? (
        <EnchantSlot
          slot={suffix}
          slotLabel="Suffix"
          headerLineIdx={headerIndices.suffix}
          effectLineIndices={effectIndices.suffix}
          lines={lines}
          onLineChange={onLineChange}
        />
      ) : groups.suffix.length > 0 ? (
        <FallbackLines slotLines={groups.suffix} onLineChange={onLineChange} />
      ) : null}
      {groups.unassigned.length > 0 && (
        <FallbackLines slotLines={groups.unassigned} onLineChange={onLineChange} />
      )}
    </div>
  );
};

export default EnchantSection;
