import React from 'react';
import { AlertTriangle } from 'lucide-react';

const DefaultSection = ({ lines, onLineChange }) => (
  <div className="space-y-2">
    {(lines || [])
      .filter(line => !line.is_header)
      .map((line, idx) => (
        <div key={idx} className="relative group">
          <input
            type="text"
            value={line.text}
            onChange={(e) => onLineChange(idx, e.target.value)}
            className={`w-full bg-gray-900 border ${line.confidence < 0.7 ? 'border-red-900/50 focus:border-red-500' : 'border-gray-700 focus:border-orange-500'} rounded px-3 py-1.5 text-sm text-gray-300 outline-none transition-colors`}
          />
          {line.confidence < 0.7 && (
            <AlertTriangle className="w-3 h-3 text-red-500 absolute right-2 top-1/2 -translate-y-1/2 opacity-50 group-hover:opacity-100 transition-opacity" title={`Low Confidence: ${Math.round(line.confidence * 100)}%`} />
          )}
        </div>
      ))}
  </div>
);

export default DefaultSection;
