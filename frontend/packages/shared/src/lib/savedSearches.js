const STORAGE_KEY = 'mabi_saved_searches';
const MAX_SAVED = 20;

const FILTER_KEYS = ['attrFilters', 'reforgeFilters', 'enchantFilters', 'echostoneFilters', 'muriasFilters'];
const SORT_KEY = { attrFilters: 'key', enchantFilters: 'name' };

function _sortByName(arr, key = 'option_name') {
  return [...arr].sort((a, b) => (a[key] || '').localeCompare(b[key] || ''));
}

export function toStorable(params) {
  const start = Math.floor(Date.now() / 1000);
  const stored = {
    tags: [...(params.tags || [])].sort(),
    gameItem: params.gameItem ? { id: params.gameItem.id, name: params.gameItem.name, type: params.gameItem.type } : null,
  };
  for (const fk of FILTER_KEYS) {
    const arr = params[fk] || [];
    stored[fk] = _sortByName(arr, SORT_KEY[fk] || 'option_name');
  }
  return stored;
}

export function isSaveable(stored) {
  return stored.tags.length > 0 || stored.gameItem
    || FILTER_KEYS.some((k) => k === 'attrFilters' ? stored[k].some((f) => f.value) : stored[k].length > 0);
}

export function hashStorable(stored) {
  const json = JSON.stringify({ ...stored, gameItem: stored.gameItem?.id || null });
  let h = 0;
  for (let i = 0; i < json.length; i++) {
    h = ((h << 5) - h + json.charCodeAt(i)) | 0;
  }
  return h.toString(36);
}

export function getSavedSearches() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

export function saveSearch(stored) {
  if (!isSaveable(stored)) return null;
  const hash = hashStorable(stored);
  const existing = getSavedSearches();
  if (existing.some((e) => e.hash === hash)) return null;

  const entry = { id: crypto.randomUUID(), hash, createdAt: new Date().toISOString(), params: stored };
  const list = [entry, ...existing].slice(0, MAX_SAVED);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  return entry;
}

export function deleteSavedSearch(id) {
  const list = getSavedSearches().filter((s) => s.id !== id);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}
