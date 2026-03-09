/**
 * RPG-style tag color tiers based on weight.
 *
 * 0-9:     Gray (hidden)
 * 10-19:   Cyan (basic)
 * 20-29:   White (common)
 * 30-39:   Green (uncommon)
 * 40-49:   Yellow (rare)
 * 50-59:   Blue (epic)
 * 60-69:   Purple (legendary)
 * 70-79:   Pink (mythic)
 * 80-89:   Orange (heroic)
 * 90-99:   Red (artifact)
 * 100-109: Holographic (divine)
 * 110-119: Rainbow (transcend)
 * 120-129: Gold foil (eternal)
 * 130-139: Neon (astral)
 * 140-149: Flame (infernal)
 * 150-159: Frost (celestial)
 * 160-169: Glitch (void)
 * 170+:    Galaxy (genesis)
 */
const TIERS = [
  { min: 170, bg: 'tag-galaxy',    text: 'text-black',   icon: 'text-purple-400',  border: 'tag-border-galaxy' },
  { min: 160, bg: 'tag-glitch',    text: 'text-black',   icon: 'text-pink-500',    border: 'tag-border-glitch' },
  { min: 150, bg: 'tag-frost',     text: 'text-black',   icon: 'text-sky-400',     border: 'tag-border-frost' },
  { min: 140, bg: 'tag-flame',     text: 'text-black',   icon: 'text-orange-500',  border: 'tag-border-flame' },
  { min: 130, bg: 'bg-gray-900',   text: 'tag-neon',     icon: 'text-cyan-400',    border: 'tag-border-neon' },
  { min: 120, bg: 'tag-gold',      text: 'text-black',   icon: 'text-yellow-500',  border: 'tag-border-gold' },
  { min: 110, bg: 'tag-rainbow',   text: 'text-black',   icon: 'text-red-500',     border: 'tag-border-rainbow' },
  { min: 100, bg: 'tag-holo',      text: 'text-black',   icon: 'text-emerald-400', border: 'tag-border-holo' },
  { min: 90,  bg: 'bg-red-900/40',     text: 'text-red-400',     icon: 'text-red-500',     border: 'border-red-700/50' },
  { min: 80,  bg: 'bg-orange-900/40',  text: 'text-orange-400',  icon: 'text-orange-500',  border: 'border-orange-700/50' },
  { min: 70,  bg: 'bg-pink-900/40',    text: 'text-pink-400',    icon: 'text-pink-500',    border: 'border-pink-700/50' },
  { min: 60,  bg: 'bg-purple-900/40',  text: 'text-purple-400',  icon: 'text-purple-500',  border: 'border-purple-700/50' },
  { min: 50,  bg: 'bg-blue-900/40',    text: 'text-blue-400',    icon: 'text-blue-500',    border: 'border-blue-700/50' },
  { min: 40,  bg: 'bg-yellow-900/40',  text: 'text-yellow-300',  icon: 'text-yellow-400',  border: 'border-yellow-700/50' },
  { min: 30,  bg: 'bg-green-900/40',   text: 'text-green-400',   icon: 'text-green-500',   border: 'border-green-700/50' },
  { min: 20,  bg: 'bg-gray-700/40',    text: 'text-gray-200',    icon: 'text-gray-300',    border: 'border-gray-500/50' },
  { min: 10,  bg: 'bg-cyan-900/40',    text: 'text-cyan-400',    icon: 'text-cyan-500',    border: 'border-cyan-700/50' },
  { min: 0,   bg: 'bg-gray-800/40',    text: 'text-gray-400',    icon: 'text-gray-500',    border: 'border-gray-600/50' },
];

const DEFAULT = TIERS[TIERS.length - 1];

export function getTagColor(weight) {
  const w = weight || 0;
  return TIERS.find(t => w >= t.min) || DEFAULT;
}
