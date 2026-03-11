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

const badgeBase = 'text-xs leading-none px-2 pt-1 pb-0.5 rounded border';
export const badgeCyan = `${badgeBase} bg-cyan-900/50 text-cyan-300 border-cyan-700/50`;
export const badgePurple = `${badgeBase} bg-purple-900/50 text-purple-300 border-purple-700/50`;
export const badgeOrange = `${badgeBase} bg-orange-900/50 text-orange-300 border-orange-700/50`;
export const badgeYellow = `${badgeBase} bg-yellow-900/50 text-yellow-300 border-yellow-700/50`;
export const badgeRed = `${badgeBase} bg-red-900/50 text-red-300 border-red-700/50`;
export const badgeBlue = `${badgeBase} bg-blue-900/50 text-blue-300 border-blue-700/50`;
export const badgeGreen = `${badgeBase} bg-green-900/50 text-green-300 border-green-700/50`;
export const badgePink = `${badgeBase} bg-pink-900/50 text-pink-300 border-pink-700/50`;
export const badgeTranscend = 'text-xs leading-none px-2 pt-1 pb-0.5 rounded border tag-rainbow text-black tag-border-rainbow font-bold';
export const badgeClickable = 'cursor-pointer hover:border-current';

/**
 * Get badge style for a level value.
 * Transcend (level > max) → rainbow, max → red, >=80% → orange, >=30% → blue, <30% → green.
 */
export function getLevelBadge(level, maxLevel, minLevel = 1) {
  if (level == null || maxLevel == null) return badgeCyan;
  const lv = +level;
  const max = +maxLevel;
  const min = +minLevel;
  if (lv > max) return badgeTranscend;
  if (lv === max) return badgeRed;
  if (max <= min) return badgeCyan;
  const pct = (lv - min) / (max - min);
  if (pct >= 0.8) return badgeOrange;
  if (pct >= 0.3) return badgeBlue;
  return badgeGreen;
}

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

// --- Pill tabs (small toggle buttons) ---

const pillBase = 'text-[10px] font-bold uppercase px-1.5 py-0.5 rounded transition-colors';
export const pillActive = `${pillBase} bg-emerald-700 text-white`;
export const pillInactive = `${pillBase} bg-gray-700 text-gray-400 hover:bg-gray-600`;

// --- Small action buttons ---

export const btnSmEmerald = 'text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-emerald-700 hover:bg-emerald-600 text-white disabled:opacity-50';

// --- Compact weight input ---

export const weightInputSm = 'text-[10px] font-bold bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5 w-12 outline-none focus:border-emerald-500';

// --- Panel sections ---

export const panelOuter = 'bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden';
export const panelHeader = 'bg-gray-700/50 px-6 py-4 flex justify-between items-center';
export const panelTitle = 'text-xl font-bold text-white';
export const panelEmpty = 'px-6 py-8 text-center text-xs text-gray-500 uppercase';

// --- Common loading / empty ---

export const loadingCenter = 'flex items-center justify-center py-20';
export const loadingIcon = 'w-8 h-8 text-cyan-500 animate-spin';
export const dividerY = 'divide-y divide-gray-700';
export const metaRow = 'flex items-center gap-2 mt-1';
export const hoverRow = 'hover:bg-gray-700/30 transition-colors';

// --- Job styles ---

export const jobRow = 'px-6 py-4 flex items-center justify-between hover:bg-gray-700/30 transition-colors';
export const jobName = 'text-sm font-bold text-white';
export const jobDesc = 'text-xs text-gray-400 mt-0.5';
export const jobMeta = 'text-[10px] text-gray-500';
export const jobMetaResult = 'text-[10px] text-gray-400';
export const jobMetaError = 'text-[10px] text-red-400 truncate max-w-xs';
export const iconSmSpin = 'w-3.5 h-3.5 animate-spin';
export const iconSm = 'w-3.5 h-3.5';
export const btnJobRun = 'flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase rounded bg-cyan-700 hover:bg-cyan-600 text-white disabled:opacity-50 transition-colors';
export const btnPagGray = 'text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded';
export const thCell = 'px-6 py-2 text-left';
export const tdCell = 'px-6 py-2';
export const tdCellMono = 'px-6 py-2 text-xs font-mono text-gray-300';
export const tdCellSub = 'px-6 py-2 text-xs text-gray-400';
export const tdCellTrunc = 'px-6 py-2 text-xs text-gray-400 max-w-xs truncate';
export const thRow = 'text-[10px] font-bold uppercase text-gray-500 border-b border-gray-700';

// --- Layout ---

export const groupRow = 'group flex justify-between items-center';
export const flexCenter = 'flex items-center gap-1';
export const effectRow = 'group flex items-center gap-1 text-xs text-gray-400';

// --- Activity logs ---

export const metaLabel = 'text-xs text-gray-400 font-mono';
export const totalLabel = 'text-xs text-gray-500 font-mono';
export const filterBar = 'px-6 py-3 border-b border-gray-700 flex flex-wrap items-center gap-3';
export const filterSelect = 'bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300 outline-none focus:border-cyan-500';
export const filterInput = 'bg-gray-900 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300 outline-none focus:border-cyan-500 w-24';
export const paginationBar = 'px-6 py-3 border-t border-gray-700 flex justify-between items-center';
export const paginationInfo = 'text-xs text-gray-500';
