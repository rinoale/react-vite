import React, { useState, useMemo } from 'react';
import { Pencil } from 'lucide-react';
import ConfigSearchInput from '../ConfigSearchInput';

const ReforgeOption = ({ opt, lineIdx, onLineChange }) => {
  const [editing, setEditing] = useState(false);

  const reforgeItems = useMemo(() => window.REFORGES_CONFIG || [], []);

  return (
    <div className="bg-gray-900/50 p-2 rounded border border-gray-700">
      {editing ? (
        <ConfigSearchInput
          items={reforgeItems}
          getLabel={(item) => item}
          onSelect={(name) => {
            const newText = opt.level != null
              ? `- ${name} (${opt.level}/${opt.max_level} 레벨)`
              : `- ${name}`;
            onLineChange(lineIdx, newText);
            setEditing(false);
          }}
          onCancel={() => setEditing(false)}
          placeholder="Search reforge option..."
        />
      ) : (
        <div className="group flex justify-between items-center mb-1">
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium text-cyan-300">{opt.name}</span>
            <button
              onClick={() => setEditing(true)}
              className="p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 hover:text-cyan-400 transition-opacity"
              title="Correct"
            >
              <Pencil className="w-3 h-3" />
            </button>
          </div>
          {opt.level != null && (
            <span className="text-xs bg-cyan-900/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-700/50">
              Level {opt.level} / {opt.max_level}
            </span>
          )}
        </div>
      )}
      {!editing && opt.effect && <p className="text-xs text-gray-400">ㄴ {opt.effect}</p>}
    </div>
  );
};

const ReforgeSection = ({ options, lines, onLineChange }) => {
  const optionLineIndices = useMemo(() => {
    if (!lines || !options?.length) return [];
    const indices = [];
    let optIdx = 0;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.is_header) continue;
      if (line.is_reforge_sub) continue;
      if (optIdx < options.length) {
        indices.push(i);
        optIdx++;
      }
    }
    return indices;
  }, [lines, options]);

  if (options?.length > 0) {
    return (
      <div className="space-y-3">
        {options.map((opt, idx) => (
          <ReforgeOption
            key={idx}
            opt={opt}
            lineIdx={optionLineIndices[idx]}
            onLineChange={onLineChange}
          />
        ))}
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
