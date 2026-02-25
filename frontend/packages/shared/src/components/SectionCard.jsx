import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

const SectionCard = ({ title, children, isOpen = true, onToggle }) => (
  <div className="bg-gray-800/50 rounded-xl border border-gray-700 overflow-hidden mb-4">
    <div
      className="bg-gray-700/50 px-4 py-2 flex justify-between items-center cursor-pointer hover:bg-gray-700 transition-colors"
      onClick={onToggle}
    >
      <h3 className="text-sm font-bold text-orange-400 uppercase tracking-wider flex items-center gap-2">
        {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        {title}
      </h3>
    </div>
    {isOpen && <div className="p-4 space-y-3">{children}</div>}
  </div>
);

export default SectionCard;
