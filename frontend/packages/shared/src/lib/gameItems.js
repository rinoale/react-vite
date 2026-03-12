/** Game item config helpers — thin wrappers over window.GAME_ITEMS_CONFIG */

export const getGameItemsConfig = () => window.GAME_ITEMS_CONFIG || [];

export const findGameItemByName = (name) =>
  getGameItemsConfig().find(gi => gi.name === name);

export const searchGameItemsLocal = (q, limit = 20) => {
  const lower = q.toLowerCase();
  return getGameItemsConfig()
    .filter(gi => gi.name.toLowerCase().includes(lower))
    .slice(0, limit);
};

/** Typed items — curated subset with type for marketplace search */

export const getTypedItemsConfig = () => window.TYPED_ITEMS_CONFIG || [];

export const searchTypedItems = (q, limit = 20) => {
  const lower = q.toLowerCase();
  return getTypedItemsConfig()
    .filter(gi => gi.name.toLowerCase().includes(lower))
    .slice(0, limit);
};

export const findTypedItem = (name) =>
  getTypedItemsConfig().find(gi => gi.name === name);

/** Type hierarchy — ancestor chain and enchant restriction matching */

const getTypeHierarchy = () => window.TYPE_HIERARCHY || {};
const getEnchantRestrictionMap = () => window.ENCHANT_RESTRICTION_MAP || {};

/**
 * Build ancestor chain for an item: Set{itemName, leafType, mid1, mid2, ..., root}
 * Walks the hierarchy tree collecting all ancestor node names for the given leaf type.
 * Leaves can appear under multiple parents (cross-cutting), so all paths are collected.
 */
export function getAncestorChain(itemName, leafType) {
  if (!leafType) return new Set(itemName ? [itemName] : []);
  const hierarchy = getTypeHierarchy();
  const ancestors = new Set();

  const walk = (node, path) => {
    if (node === null || node === undefined) return;
    if (typeof node !== 'object') return;
    for (const [key, value] of Object.entries(node)) {
      if (value === null) {
        if (key === leafType) {
          for (const p of path) ancestors.add(p);
        }
      } else {
        walk(value, [...path, key]);
      }
    }
  };

  walk(hierarchy, []);
  ancestors.add(leafType);
  if (itemName && itemName !== leafType) ancestors.add(itemName);
  return ancestors;
}

/**
 * Filter enchants applicable to an item based on restriction mapping.
 * Returns enchants where: no restriction (universal) OR restriction nodes ∩ ancestor chain ≠ ∅
 */
export function filterEnchantsByRestriction(enchants, itemName, leafType) {
  if (!leafType) return enchants;
  const chain = getAncestorChain(itemName, leafType);
  const restrictionMap = getEnchantRestrictionMap();

  return enchants.filter((enchant) => {
    if (!enchant.restriction) return true;
    const nodes = restrictionMap[enchant.restriction];
    if (!nodes) return false;
    return nodes.some((node) => chain.has(node));
  });
}
