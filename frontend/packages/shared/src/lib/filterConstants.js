/* Filter constants shared between ChipFilterPanel and ListingSearchBar */

import { getAncestorChain } from './gameItems.js';

export const FILTER_OPTIONS = [
  { key: 'erg_level', i18nKey: 'marketplace.filter.ergLevel', abbr: 'ERG', kind: 'erg' },
  { key: 'special_upgrade_level', i18nKey: 'marketplace.filter.specialUpgrade', abbr: 'SU', kind: 'special_upgrade' },
  { key: 'damage', i18nKey: 'attrs.damage', abbr: 'Atk', kind: 'attr' },
  { key: 'magic_damage', i18nKey: 'attrs.magic_damage', abbr: 'MA', kind: 'attr' },
  { key: 'balance', i18nKey: 'attrs.balance', abbr: 'Bal', kind: 'attr' },
  { key: 'defense', i18nKey: 'attrs.defense', abbr: 'Def', kind: 'attr' },
  { key: 'protection', i18nKey: 'attrs.protection', abbr: 'Pro', kind: 'attr' },
  { key: 'magic_defense', i18nKey: 'attrs.magic_defense', abbr: 'MDef', kind: 'attr' },
  { key: 'magic_protection', i18nKey: 'attrs.magic_protection', abbr: 'MPro', kind: 'attr' },
  { key: 'additional_damage', i18nKey: 'attrs.additional_damage', abbr: 'Add', kind: 'attr' },
];

export const FILTER_MAP = Object.fromEntries(FILTER_OPTIONS.map((c) => [c.key, c]));

export const ERG_GRADES = ['S', 'A', 'B'];
export const SPECIAL_UPGRADE_TYPES = ['R', 'S'];

export const OPS = ['gte', 'lte', 'eq'];
export const OP_SYMBOLS = { gte: '\u2265', lte: '\u2264', eq: '=' };

/* ── Item type → available filter keys (hierarchy-based) ── */

const ANCESTOR_ATTR_RULES = [
  { node: '무기', attrs: ['damage', 'balance'] },
  { node: '방어구', attrs: ['defense', 'protection', 'magic_defense', 'magic_protection'] },
  { node: '마법', attrs: ['magic_damage'] },
  { node: '대형 낫', attrs: ['additional_damage'] },
];

const ALL_ATTRS = FILTER_OPTIONS.filter((o) => o.kind === 'attr').map((o) => o.key);

/**
 * Get available filter keys for an item type (leaf tag from type_hierarchy).
 * Uses ancestor chain to accumulate attrs from matching hierarchy nodes.
 * Returns { attrs: string[], enchant: bool, reforge: bool, erg: bool, su: bool, echostone: bool, murias: bool }
 */
export function getFiltersForItemType(type) {
  if (!type) {
    return { attrs: ALL_ATTRS, enchant: true, reforge: true, erg: true, su: true, echostone: false, murias: false };
  }

  const chain = getAncestorChain(null, type);

  if (chain.has('에코스톤')) {
    return { attrs: [], enchant: false, reforge: false, erg: false, su: false, echostone: true, murias: false };
  }

  if (chain.has('무리아스의 유물')) {
    return { attrs: [], enchant: false, reforge: false, erg: false, su: false, echostone: false, murias: true };
  }

  const attrs = [];
  for (const rule of ANCESTOR_ATTR_RULES) {
    if (chain.has(rule.node)) {
      for (const a of rule.attrs) {
        if (!attrs.includes(a)) attrs.push(a);
      }
    }
  }

  if (chain.has('액세서리')) {
    return { attrs, enchant: true, reforge: true, erg: false, su: false, echostone: false, murias: false };
  }

  return { attrs, enchant: true, reforge: true, erg: true, su: true, echostone: false, murias: false };
}

/** Map echostone leaf type to color for ECHOSTONE_CONFIG filtering */
export const ECHOSTONE_TYPE_TO_COLOR = {
  '레드 에코스톤': 'red',
  '블루 에코스톤': 'blue',
  '옐로 에코스톤': 'yellow',
  '블랙 에코스톤': 'black',
  '실버 에코스톤': 'silver',
};
