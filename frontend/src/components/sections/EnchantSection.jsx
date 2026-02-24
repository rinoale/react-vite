import React, { useMemo } from 'react';

const EnchantSlot = ({ slot, slotLabel }) => {
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
        {slot.effects.map((eff, i) => (
          <p key={i} className="text-xs text-gray-400">
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
          </p>
        ))}
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
  const groups = useMemo(() => {
    if (!lines) return { prefix: [], suffix: [], unassigned: [] };

    let currentSlot = null;
    const result = { prefix: [], suffix: [], unassigned: [] };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const text = line.text || '';
      if (text.startsWith('[접두]')) currentSlot = 'prefix';
      else if (text.startsWith('[접미]')) currentSlot = 'suffix';
      result[currentSlot || 'unassigned'].push({ ...line, lineIdx: i });
    }

    return result;
  }, [lines]);

  return (
    <div className="space-y-3">
      {prefix ? (
        <EnchantSlot slot={prefix} slotLabel="Prefix" />
      ) : groups.prefix.length > 0 ? (
        <FallbackLines slotLines={groups.prefix} onLineChange={onLineChange} />
      ) : null}
      {suffix ? (
        <EnchantSlot slot={suffix} slotLabel="Suffix" />
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
