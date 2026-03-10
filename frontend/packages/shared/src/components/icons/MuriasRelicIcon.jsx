import React from 'react';

const MuriasRelicIcon = ({ className = 'w-4 h-4' }) => (
  <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    {/* outer frame */}
    <rect x="2" y="2" width="28" height="28" rx="2" fill="#8B6914" stroke="#5C4A0E" strokeWidth="1.5" />
    <rect x="4" y="4" width="24" height="24" rx="1" fill="#A67C1A" stroke="#C49B2A" strokeWidth="0.5" />

    {/* corner ornaments */}
    <circle cx="7" cy="7" r="1.5" fill="#D4A832" />
    <circle cx="25" cy="7" r="1.5" fill="#D4A832" />
    <circle cx="7" cy="25" r="1.5" fill="#D4A832" />
    <circle cx="25" cy="25" r="1.5" fill="#D4A832" />

    {/* celtic knot ring */}
    <circle cx="16" cy="16" r="7" stroke="#D4A832" strokeWidth="2" fill="none" />
    <circle cx="16" cy="16" r="5" stroke="#8B6914" strokeWidth="1" fill="none" />

    {/* knot interlace pattern */}
    <path d="M12 12 Q16 9, 20 12 Q23 16, 20 20 Q16 23, 12 20 Q9 16, 12 12Z" stroke="#EECC55" strokeWidth="1.2" fill="none" />
    <path d="M16 9 L16 23 M9 16 L23 16" stroke="#D4A832" strokeWidth="0.8" opacity="0.6" />

    {/* center gem */}
    <circle cx="16" cy="16" r="2" fill="#EECC55" />
    <circle cx="15.5" cy="15.5" r="0.8" fill="#FFF5CC" opacity="0.7" />
  </svg>
);

export default MuriasRelicIcon;
