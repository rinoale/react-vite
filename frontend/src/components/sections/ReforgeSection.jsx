import React, { useMemo } from 'react';

const ReforgeSection = ({ options, lines, onLineChange, onStructuredChange }) => {
  // Map each option to its line index in the lines array
  const optionLineIndices = useMemo(() => {
    if (!lines || !options?.length) return [];
    const indices = [];
    let optIdx = 0;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.is_header) continue;
      if (line.is_reforge_sub) continue;
      // This is a main option line
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
        {options.map((opt, idx) => {
          const lineIdx = optionLineIndices[idx];
          return (
            <div key={idx} className="bg-gray-900/50 p-2 rounded border border-gray-700">
              <div className="flex justify-between items-center mb-1">
                <input
                  type="text"
                  value={opt.name}
                  onChange={(e) => {
                    const newName = e.target.value;
                    const newText = opt.level != null
                      ? `- ${newName} (${opt.level}/${opt.max_level} 레벨)`
                      : `- ${newName}`;
                    if (onStructuredChange) {
                      onStructuredChange(lineIdx, newText, idx, (option) => {
                        option.name = newName;
                        option.option_name = newName;
                      });
                    } else {
                      onLineChange(lineIdx, newText);
                    }
                  }}
                  className="bg-transparent border-b border-gray-700 text-sm font-medium text-cyan-300 px-1 py-0.5 focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 outline-none"
                />
                {opt.level != null && (
                  <span className="flex items-center gap-1 text-xs bg-cyan-900/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-700/50">
                    Level{' '}
                    <input
                      type="number"
                      value={opt.level}
                      min={1}
                      max={opt.max_level || 20}
                      onChange={(e) => {
                        const val = e.target.value;
                        const newLevel = val === '' ? '' : Number(val);
                        const newText = `- ${opt.name} (${val}/${opt.max_level} 레벨)`;
                        if (onStructuredChange) {
                          onStructuredChange(lineIdx, newText, idx, (option) => {
                            option.level = newLevel;
                            option.option_level = newLevel;
                          });
                        } else {
                          onLineChange(lineIdx, newText);
                        }
                      }}
                      className="w-10 bg-gray-900 border border-gray-700 rounded px-1 py-0 text-center text-cyan-300 font-bold focus:ring-1 focus:ring-cyan-500 outline-none [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    />
                    <span>/ {opt.max_level}</span>
                  </span>
                )}
              </div>
              {opt.effect && <p className="text-xs text-gray-400">ㄴ {opt.effect}</p>}
            </div>
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
