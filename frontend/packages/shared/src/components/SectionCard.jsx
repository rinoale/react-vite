import React from 'react';
import { ChevronDown, ChevronRight, X } from 'lucide-react';

const SectionCard = ({ title, children, isOpen = true, onToggle, onRemove }) => (
  <div className="bg-gray-800/50 rounded-xl border border-gray-700 mb-4">
    <div
      className="bg-gray-700/50 px-4 py-2 flex justify-between items-center cursor-pointer hover:bg-gray-700 transition-colors rounded-t-xl"
      onClick={onToggle}
    >
      <h3 className="text-sm font-bold text-orange-400 uppercase tracking-wider flex items-center gap-2">
        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        {title}
      </h3>
      {onRemove && (
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="p-1 text-gray-500 hover:text-red-400 transition-colors"
          title="Remove section"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
    {isOpen && <div className="p-4 space-y-3">{children}</div>}
  </div>
);

export default SectionCard;
