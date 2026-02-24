import React from 'react';

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

const EnchantSection = ({ prefix, suffix, lines, onLineChange }) => (
  <div className="space-y-3">
    <EnchantSlot slot={prefix} slotLabel="Prefix" />
    <EnchantSlot slot={suffix} slotLabel="Suffix" />
    {!prefix && !suffix && lines?.filter(l => !l.is_header).map((line, idx) => (
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

export default EnchantSection;
