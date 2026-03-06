/**
 * RPG-style tag color tiers based on weight (0-99).
 *
 * 0-9: Gray (hidden/search)
 * 10-19: White (common)
 * 20-29: Green (uncommon)
 * 30-39: Blue (rare)
 * 40-49: Purple (epic)
 * 50-59: Pink (heroic)
 * 60-69: Orange (legendary)
 * 70-79: Gold (mythic)
 * 80-99: Red (artifact)
 */
const TIERS = [
  { min: 80, bg: 'bg-red-900/40',    text: 'text-red-400',    icon: 'text-red-500' },
  { min: 70, bg: 'bg-yellow-900/40',  text: 'text-yellow-300', icon: 'text-yellow-400' },
  { min: 60, bg: 'bg-orange-900/40',  text: 'text-orange-400', icon: 'text-orange-500' },
  { min: 50, bg: 'bg-pink-900/40',    text: 'text-pink-400',   icon: 'text-pink-500' },
  { min: 40, bg: 'bg-purple-900/40',  text: 'text-purple-400', icon: 'text-purple-500' },
  { min: 30, bg: 'bg-blue-900/40',    text: 'text-blue-400',   icon: 'text-blue-500' },
  { min: 20, bg: 'bg-green-900/40',   text: 'text-green-400',  icon: 'text-green-500' },
  { min: 10, bg: 'bg-gray-700/40',    text: 'text-gray-200',   icon: 'text-gray-300' },
  { min: 0,  bg: 'bg-gray-800/40',    text: 'text-gray-400',   icon: 'text-gray-500' },
];

const DEFAULT = TIERS[TIERS.length - 1];

export function getTagColor(weight) {
  const w = weight || 0;
  return TIERS.find(t => w >= t.min) || DEFAULT;
}
