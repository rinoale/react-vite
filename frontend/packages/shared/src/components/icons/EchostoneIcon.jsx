import React from 'react';

const COLOR_MAP = {
  red: { gem: '#E53E3E', gemLight: '#FC8181', gemDark: '#9B2C2C', shine: '#FEB2B2', glow: '#E53E3E' },
  blue: { gem: '#3B9EE8', gemLight: '#7EC8F8', gemDark: '#1A5FA0', shine: '#D6EEFF', glow: '#3B9EE8' },
  yellow: { gem: '#10B981', gemLight: '#6EE7B7', gemDark: '#065F46', shine: '#D1FAE5', glow: '#10B981' },
  black: { gem: '#4A5568', gemLight: '#8899AA', gemDark: '#1A202C', shine: '#CBD5E0', glow: '#4A5568' },
  silver: { gem: '#A0AEC0', gemLight: '#D4DEE8', gemDark: '#4A5568', shine: '#F0F4F8', glow: '#A0AEC0' },
};

const EchostoneIcon = ({ color = 'red', className = 'w-4 h-4' }) => {
  const c = COLOR_MAP[color] || COLOR_MAP.red;
  const id = `echo-${color}`;

  return (
    <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
      <defs>
        {/* golden frame gradient */}
        <linearGradient id={`${id}-gold`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#F5D87A" />
          <stop offset="40%" stopColor="#C8952E" />
          <stop offset="70%" stopColor="#F5D87A" />
          <stop offset="100%" stopColor="#A67C1A" />
        </linearGradient>
        {/* gem radial gradient */}
        <radialGradient id={`${id}-gem`} cx="0.4" cy="0.35" r="0.6">
          <stop offset="0%" stopColor={c.gemLight} />
          <stop offset="50%" stopColor={c.gem} />
          <stop offset="100%" stopColor={c.gemDark} />
        </radialGradient>
        {/* glow filter */}
        <filter id={`${id}-glow`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" />
        </filter>
      </defs>

      {/* outer glow behind frame */}
      <polygon
        points="32,4 50,13 56,32 50,51 32,60 14,51 8,32 14,13"
        fill={c.glow}
        opacity="0.15"
        filter={`url(#${id}-glow)`}
      />

      {/* hexagonal star frame — 6 pointed ornamental tips */}
      <polygon
        points="32,2 38,12 52,10 44,20 56,32 44,44 52,54 38,52 32,62 26,52 12,54 20,44 8,32 20,20 12,10 26,12"
        fill={`url(#${id}-gold)`}
        stroke="#8B6914"
        strokeWidth="1"
      />
      {/* inner gold bevel highlight */}
      <polygon
        points="32,6 37,14 48,12 42,21 52,32 42,43 48,52 37,50 32,58 27,50 16,52 22,43 12,32 22,21 16,12 27,14"
        fill="none"
        stroke="#F5E6A8"
        strokeWidth="0.6"
        opacity="0.6"
      />

      {/* white inner background */}
      <polygon
        points="32,14 42,20 46,32 42,44 32,50 22,44 18,32 22,20"
        fill="#F8F4E8"
        stroke="#C8952E"
        strokeWidth="0.8"
      />

      {/* gem — hexagonal faceted jewel */}
      <polygon
        points="32,16 41,22 44,32 41,42 32,48 23,42 20,32 23,22"
        fill={`url(#${id}-gem)`}
        stroke={c.gemDark}
        strokeWidth="0.8"
      />

      {/* gem facet lines */}
      <line x1="32" y1="16" x2="32" y2="32" stroke={c.gemLight} strokeWidth="0.5" opacity="0.5" />
      <line x1="41" y1="22" x2="32" y2="32" stroke={c.gemLight} strokeWidth="0.5" opacity="0.4" />
      <line x1="44" y1="32" x2="32" y2="32" stroke={c.gemDark} strokeWidth="0.5" opacity="0.3" />
      <line x1="41" y1="42" x2="32" y2="32" stroke={c.gemDark} strokeWidth="0.5" opacity="0.3" />
      <line x1="32" y1="48" x2="32" y2="32" stroke={c.gemDark} strokeWidth="0.5" opacity="0.4" />
      <line x1="23" y1="42" x2="32" y2="32" stroke={c.gemDark} strokeWidth="0.5" opacity="0.3" />
      <line x1="20" y1="32" x2="32" y2="32" stroke={c.gemLight} strokeWidth="0.5" opacity="0.4" />
      <line x1="23" y1="22" x2="32" y2="32" stroke={c.gemLight} strokeWidth="0.5" opacity="0.5" />

      {/* top-left highlight facet */}
      <polygon
        points="32,16 23,22 20,32 32,32"
        fill={c.gemLight}
        opacity="0.35"
      />
      <polygon
        points="32,16 41,22 32,32"
        fill={c.shine}
        opacity="0.2"
      />

      {/* bottom-right shadow facet */}
      <polygon
        points="44,32 41,42 32,48 32,32"
        fill={c.gemDark}
        opacity="0.3"
      />

      {/* sparkle / shine */}
      <circle cx="27" cy="24" r="2.5" fill="white" opacity="0.7" />
      <circle cx="27" cy="24" r="1.2" fill="white" opacity="0.9" />
      {/* cross sparkle */}
      <line x1="27" y1="20" x2="27" y2="28" stroke="white" strokeWidth="0.6" opacity="0.5" />
      <line x1="23" y1="24" x2="31" y2="24" stroke="white" strokeWidth="0.6" opacity="0.5" />
    </svg>
  );
};

export default EchostoneIcon;
