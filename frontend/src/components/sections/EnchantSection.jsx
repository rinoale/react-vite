import React, { useState, useMemo } from 'react';
import { Pencil } from 'lucide-react';
import ConfigSearchInput from '../ConfigSearchInput';

function replaceFirstNumber(text, newValue) {
  return text.replace(/\d+(\.\d+)?/, String(newValue));
}

function extractFirstNumber(text) {
  const m = text.match(/\d+(\.\d+)?/);
  return m ? m[0] : null;
}

/** Find enchant config entry matching name + slot */
function findEnchantConfig(name, slotInt) {
  return (window.ENCHANTS_CONFIG || []).find(
    e => e.name === name && e.slot === slotInt
  );
}

const EffectRow = ({ eff, lineIdx, lineText, onLineChange, configEffects }) => {
  const [editing, setEditing] = useState(false);

  if (editing) {
    if (configEffects && configEffects.length > 0) {
      // Search/select from config effects
      return (
        <div className="flex items-center gap-1">
          <span className="text-gray-600 mr-1">-</span>
          <ConfigSearchInput
            items={configEffects}
            getLabel={(item) => item}
            onSelect={(selected) => {
              // Preserve OCR'd number, replace text template
              const ocrNumber = extractFirstNumber(lineText);
              let newEffText = selected;
              if (ocrNumber !== null) {
                newEffText = replaceFirstNumber(selected, ocrNumber);
              }
              onLineChange(lineIdx, '- ' + newEffText);
              setEditing(false);
            }}
            onCancel={() => setEditing(false)}
            placeholder="Search effect..."
          />
        </div>
      );
    }
    // Fallback: text input when no config effects available
    return (
      <div className="flex items-center gap-1">
        <span className="text-gray-600 mr-1">-</span>
        <input
          type="text"
          defaultValue={lineText}
          autoFocus
          onKeyDown={(e) => {
            if (e.key === 'Enter') { onLineChange(lineIdx, e.target.value); setEditing(false); }
            if (e.key === 'Escape') setEditing(false);
          }}
          className="flex-1 bg-gray-900 border border-orange-500 rounded px-2 py-1 text-xs text-gray-200 focus:ring-1 focus:ring-orange-500 outline-none"
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
          <span className="text-orange-400 font-bold">{eff.option_level}</span>
          {eff.text.slice(eff.text.indexOf(String(eff.option_level)) + String(eff.option_level).length).trim() && (
            <span> {eff.text.slice(eff.text.indexOf(String(eff.option_level)) + String(eff.option_level).length).trim()}</span>
          )}
        </>
      ) : (
        <span>{eff.text}</span>
      )}
      <button
        onClick={() => setEditing(true)}
        className="ml-auto p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-orange-400 transition-opacity"
        title="Correct"
      >
        <Pencil className="w-3 h-3" />
      </button>
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

  // Get effects from config for the currently identified enchant
  const configEffects = useMemo(() => {
    if (!slot) return null;
    const cfg = findEnchantConfig(slot.name, slotInt);
    return cfg?.effects || null;
  }, [slot, slotInt]);

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
              const newText = `[${slotKor}] ${item.name} (랭크 ${item.rank_label})`;
              onLineChange(headerLineIdx, newText);
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
          return (
            <EffectRow
              key={i}
              eff={eff}
              lineIdx={lineIdx}
              lineText={lineText}
              onLineChange={onLineChange}
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
