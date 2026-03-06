import React, { useState, useRef } from 'react';
import { Hash, X } from 'lucide-react';
import { getTagColor } from '@mabi/shared/lib/tagColors';

const TAG_WEIGHTS = [80, 60, 30];

const TagEditor = ({ tags, onTagsChange, maxTags = 3, maxLength = 5 }) => {
  const [tagInput, setTagInput] = useState('');
  const [tagAdding, setTagAdding] = useState(false);
  const [blinkIdx, setBlinkIdx] = useState(null);
  const tagInputRef = useRef(null);

  const addTag = () => {
    const tag = tagInput.trim().slice(0, maxLength);
    if (!tag || tags.length >= maxTags) return;
    const dupIdx = tags.indexOf(tag);
    if (dupIdx !== -1) {
      setBlinkIdx(dupIdx);
      setTimeout(() => setBlinkIdx(null), 600);
      return;
    }
    onTagsChange([...tags, tag]);
    setTagInput('');
    setTagAdding(false);
  };

  const removeTag = (idx) => {
    onTagsChange(tags.filter((_, i) => i !== idx));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); addTag(); }
    if (e.key === 'Escape') { setTagAdding(false); setTagInput(''); }
  };

  const handleBlur = () => {
    if (!tagInput.trim()) { setTagAdding(false); setTagInput(''); }
  };

  const startAdding = () => {
    setTagAdding(true);
    setTimeout(() => tagInputRef.current?.focus(), 0);
  };

  const nextColor = getTagColor(TAG_WEIGHTS[tags.length] || 0);

  return (
    <div className="mt-4">
      <div className="flex items-center gap-2 flex-wrap">
        {tags.map((tag, idx) => {
          const c = getTagColor(TAG_WEIGHTS[idx] || 0);
          return (
            <span key={idx} className={`inline-flex items-center gap-0.5 text-sm font-bold pl-1.5 pr-1 py-1 rounded-full ${c.bg} ${c.text} ${blinkIdx === idx ? 'animate-blink-twice' : ''}`}>
              <Hash className={`w-3.5 h-3.5 ${c.icon}`} />
              {tag}
              <button type="button" onClick={() => removeTag(idx)} className="ml-0.5 p-0.5 rounded-full hover:bg-red-900/40 hover:text-red-400 transition-colors">
                <X className="w-3 h-3" />
              </button>
            </span>
          );
        })}
        {tags.length < maxTags && (tagAdding ? (
          <span className="inline-flex items-center gap-0.5 text-sm py-1 pl-1.5 pr-1 rounded-full bg-gray-800">
            <Hash className={`w-3.5 h-3.5 ${nextColor.icon}`} />
            <input
              ref={tagInputRef}
              type="text"
              maxLength={maxLength}
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={handleBlur}
              className="bg-transparent text-sm text-white outline-none w-16"
            />
          </span>
        ) : (
          <button type="button" onClick={startAdding} className="p-1.5 rounded-full cursor-pointer hover:bg-gray-700 transition-colors">
            <Hash className={`w-4 h-4 ${nextColor.icon}`} />
          </button>
        ))}
      </div>
    </div>
  );
};

export default TagEditor;
