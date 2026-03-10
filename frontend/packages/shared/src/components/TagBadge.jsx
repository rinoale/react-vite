import React from 'react';
import { X } from 'lucide-react';
import { getTagColor } from '../lib/tagColors.js';

const SIZE = {
  xs: 'text-xs leading-none px-2 pt-1 pb-0.5',
  sm: 'text-sm leading-none px-2 pt-1 pb-0.5',
};

/**
 * Weight-colored tag badge. Optionally removable.
 *
 * @param {string}   name     - tag display name
 * @param {number}   weight   - tag weight (determines color tier)
 * @param {'xs'|'sm'} size    - text size (default 'xs')
 * @param {function} [onRemove] - if provided, renders an X button
 * @param {string}   [className] - extra classes appended
 */
const TagBadge = ({ name, weight = 0, size = 'xs', onRemove, onClick, className = '' }) => {
  const c = getTagColor(weight);
  return (
    <span onClick={onClick} className={`inline-flex items-center gap-1 border rounded-full font-semibold whitespace-nowrap ${onClick ? 'cursor-pointer' : 'cursor-default'} ${SIZE[size] || SIZE.xs} ${c.bg} ${c.text} ${c.border} ${className}`}>
      {name}
      {onRemove && (
        <button onClick={onRemove} className="hover:text-white">
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  );
};

export default TagBadge;
