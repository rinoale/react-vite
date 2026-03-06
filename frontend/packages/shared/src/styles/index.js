// --- Inputs ---

export const inputBase = 'w-full bg-gray-900 border rounded px-3 py-1.5 text-sm text-gray-300 outline-none transition-colors';
export const inputDefault = `${inputBase} border-gray-700 focus:border-orange-500`;
export const inputLowConf = `${inputBase} border-red-900/50 focus:border-red-500`;
export const inputCompact = 'w-full bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-300 focus:ring-1 focus:ring-orange-500 outline-none';
export const editNumber = 'w-12 text-orange-400 font-bold bg-gray-900 border border-orange-500 rounded px-1 text-xs text-center outline-none';
export const editLevelCyan = 'w-16 text-xs text-cyan-300 bg-gray-900 border border-cyan-500 rounded px-1 py-0.5 text-center outline-none';

// --- Icon buttons (hover-reveal inside group) ---

const iconBtnBase = 'p-0.5 text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity';
export const iconBtnEdit = `${iconBtnBase} hover:text-cyan-400`;
export const iconBtnEditPurple = `${iconBtnBase} hover:text-purple-400`;
export const iconBtnEditOrange = `${iconBtnBase} hover:text-orange-400`;
export const iconBtnRemove = `${iconBtnBase} hover:text-red-400`;

// --- Cards & containers ---

export const cardItem = 'bg-gray-900/50 p-2 rounded border border-gray-700';
export const cardSlot = 'bg-gray-900/50 p-3 rounded border border-gray-700';

// --- Badges ---

const badgeBase = 'text-xs px-2 py-0.5 rounded border';
export const badgeCyan = `${badgeBase} bg-cyan-900/50 text-cyan-300 border-cyan-700/50`;
export const badgePurple = `${badgeBase} bg-purple-900/50 text-purple-300 border-purple-700/50`;
export const badgeOrange = `${badgeBase} bg-orange-900/50 text-orange-300 border-orange-700/50`;
export const badgeYellow = `${badgeBase} bg-yellow-900/50 text-yellow-300 border-yellow-700/50`;
export const badgePink = `${badgeBase} bg-pink-900/50 text-pink-300 border-pink-700/50`;
export const badgeClickable = 'cursor-pointer hover:border-current';

// --- Dashed add buttons ---

const addBtnBase = 'w-full border-2 border-dashed border-gray-700 rounded-lg p-3 text-sm text-gray-500 transition-colors flex items-center justify-center gap-2';
export const addBtnCyan = `${addBtnBase} hover:border-cyan-500 hover:text-cyan-300`;
export const addBtnPurple = `${addBtnBase} hover:border-purple-500 hover:text-purple-300`;

// --- Dropdowns ---

export const dropdownBase = 'absolute z-50 mt-1 bg-gray-800 border border-gray-600 rounded shadow-lg overflow-auto max-h-48 scrollbar-thin';
export const dropdownFull = `${dropdownBase} w-full`;
export const dropdownInline = `${dropdownBase} min-w-[6rem]`;
export const dropdownOption = 'px-2 py-1.5 text-sm cursor-pointer';
export const dropdownOptionCompact = 'px-2 py-1 text-sm cursor-pointer';
export const dropdownTrigger = 'flex items-center justify-between gap-1 cursor-pointer bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500 transition-colors';
export const dropdownTriggerInline = 'inline-flex items-center gap-0.5 cursor-pointer font-bold focus:outline-none';

// --- Positioned buttons ---

export const clearBtnAbsolute = 'absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-white';

// --- Layout ---

export const groupRow = 'group flex justify-between items-center';
export const flexCenter = 'flex items-center gap-1';
export const effectRow = 'group flex items-center gap-1 text-xs text-gray-400';
