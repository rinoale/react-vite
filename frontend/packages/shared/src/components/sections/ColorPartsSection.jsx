import React from 'react';

const ColorPartsSection = ({ parts }) => (
  <div className="grid grid-cols-3 gap-2">
    {parts.map((p, idx) => (
      <div key={idx} className="bg-gray-900 p-2 rounded border border-gray-700 flex items-center gap-3">
        <div
          className="w-8 h-8 rounded border border-white/20"
          style={{ backgroundColor: `rgb(${p.r || 0}, ${p.g || 0}, ${p.b || 0})` }}
          title={`R:${p.r} G:${p.g} B:${p.b}`}
        />
        <div>
          <span className="text-xs font-bold text-gray-400">Part {p.part}</span>
          <div className="text-[10px] text-gray-500">
            {p.r},{p.g},{p.b}
          </div>
        </div>
      </div>
    ))}
  </div>
);

export default ColorPartsSection;
