import React from 'react';

const ReforgeSection = ({ options, lines, onLineChange }) => (
  <div className="space-y-3">
    {options.map((opt, idx) => (
      <div key={idx} className="bg-gray-900/50 p-2 rounded border border-gray-700">
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm font-medium text-cyan-300">{opt.name}</span>
          <span className="text-xs bg-cyan-900/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-700/50">
            Level {opt.level} / {opt.max_level}
          </span>
        </div>
        {opt.effect && <p className="text-xs text-gray-400">ㄴ {opt.effect}</p>}
      </div>
    ))}
    {!options.length && lines?.map((line, idx) => (
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

export default ReforgeSection;
