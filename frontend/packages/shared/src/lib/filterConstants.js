/* Filter constants shared between ChipFilterPanel and ListingSearchBar */

export const FILTER_OPTIONS = [
  { key: 'erg_level', i18nKey: 'marketplace.filter.ergLevel', abbr: 'ERG', kind: 'erg' },
  { key: 'special_upgrade_level', i18nKey: 'marketplace.filter.specialUpgrade', abbr: 'SU', kind: 'special_upgrade' },
  { key: 'damage', i18nKey: 'attrs.damage', abbr: 'Atk', kind: 'attr' },
  { key: 'magic_damage', i18nKey: 'attrs.magic_damage', abbr: 'MA', kind: 'attr' },
  { key: 'balance', i18nKey: 'attrs.balance', abbr: 'Bal', kind: 'attr' },
  { key: 'defense', i18nKey: 'attrs.defense', abbr: 'Def', kind: 'attr' },
  { key: 'protection', i18nKey: 'attrs.protection', abbr: 'Pro', kind: 'attr' },
  { key: 'durability', i18nKey: 'attrs.durability', abbr: 'Dur', kind: 'attr' },
  { key: 'piercing_level', i18nKey: 'attrs.piercing_level', abbr: 'Prc', kind: 'attr' },
];

export const FILTER_MAP = Object.fromEntries(FILTER_OPTIONS.map((c) => [c.key, c]));

export const ERG_GRADES = ['S', 'A', 'B'];
export const SPECIAL_UPGRADE_TYPES = ['R', 'S'];

export const OPS = ['gte', 'lte', 'eq'];
export const OP_SYMBOLS = { gte: '\u2265', lte: '\u2264', eq: '=' };
