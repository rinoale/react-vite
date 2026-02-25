import React, { useMemo } from 'react';

function replaceNumber(text, newValue) {
  return text.replace(/\d+(\.\d+)?/, String(newValue));
}

const EnchantSlot = ({ slot, slotLabel, effectLineIndices, onLineChange }) => {
  if (!slot) return null;
  return (
    <div className="bg-gray-900/50 p-3 rounded border border-gray-700">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-purple-300">{slot.name}</span>
        <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded border border-purple-700/50">
          {slotLabel} · Rank {slot.rank}
        </span>
      </div>
      <div className="space-y-1.5 pl-3 border-l border-purple-900/30">
        {slot.effects.map((eff, i) => {
          const lineIdx = effectLineIndices[i];
          return (
            <div key={i} className="flex items-center gap-1 text-xs text-gray-400">
              <span className="text-gray-600 mr-1">-</span>
              {eff.option_name != null ? (
                <>
                  <span className="whitespace-nowrap">{eff.option_name}</span>
                  <input
                    type="number"
                    value={eff.option_level}
                    onChange={(e) => {
                      const val = e.target.value;
                      const newText = replaceNumber(eff.text, val);
                      onLineChange(lineIdx, '- ' + newText, (section) => {
                        section.effects[i].option_level = val === '' ? '' : Number(val);
                        section.effects[i].text = newText;
                      });
                    }}
                    className="w-16 bg-gray-900 border border-gray-700 rounded px-1.5 py-0.5 text-center text-orange-400 font-bold focus:ring-1 focus:ring-orange-500 outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                  />
                  {eff.text.slice(eff.text.indexOf(String(eff.option_level)) + String(eff.option_level).length).trim() && (
                    <span className="whitespace-nowrap">
                      {eff.text.slice(eff.text.indexOf(String(eff.option_level)) + String(eff.option_level).length).trim()}
                    </span>
                  )}
                </>
              ) : (
                <input
                  type="text"
                  value={eff.text}
                  onChange={(e) => {
                    onLineChange(lineIdx, '- ' + e.target.value, (section) => {
                      section.effects[i].text = e.target.value;
                    });
                  }}
                  className="flex-1 bg-gray-900 border border-gray-700 rounded px-2 py-0.5 text-gray-300 focus:ring-1 focus:ring-orange-500 outline-none"
                />
              )}
            </div>
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

const EnchantSection = ({ prefix, suffix, lines, onLineChange, onStructuredChange }) => {
  // Build mapping from structured effects to line indices
  const { groups, effectIndices } = useMemo(() => {
    if (!lines) return { groups: { prefix: [], suffix: [], unassigned: [] }, effectIndices: { prefix: [], suffix: [] } };

    let currentSlot = null;
    const grp = { prefix: [], suffix: [], unassigned: [] };
    const effIdx = { prefix: [], suffix: [] };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const text = line.text || '';
      if (text.startsWith('[접두]')) currentSlot = 'prefix';
      else if (text.startsWith('[접미]')) currentSlot = 'suffix';
      grp[currentSlot || 'unassigned'].push({ ...line, lineIdx: i });

      // Non-header lines in a slot = effects
      if (currentSlot && !text.startsWith('[접두]') && !text.startsWith('[접미]')) {
        effIdx[currentSlot].push(i);
      }
    }

    return { groups: grp, effectIndices: effIdx };
  }, [lines]);

  const handleSlotLineChange = (slotKey) => (lineIdx, newText, effectUpdater) => {
    if (onStructuredChange && effectUpdater) {
      onStructuredChange(lineIdx, newText, slotKey, effectUpdater);
    } else {
      onLineChange(lineIdx, newText);
    }
  };

  return (
    <div className="space-y-3">
      {prefix ? (
        <EnchantSlot
          slot={prefix}
          slotLabel="Prefix"
          effectLineIndices={effectIndices.prefix}
          onLineChange={handleSlotLineChange('prefix')}
        />
      ) : groups.prefix.length > 0 ? (
        <FallbackLines slotLines={groups.prefix} onLineChange={onLineChange} />
      ) : null}
      {suffix ? (
        <EnchantSlot
          slot={suffix}
          slotLabel="Suffix"
          effectLineIndices={effectIndices.suffix}
          onLineChange={handleSlotLineChange('suffix')}
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
