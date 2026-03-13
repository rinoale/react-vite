/** Schema constants for auto-tag rule builder. */

/**
 * All listing-related tables and their referable columns.
 * Plural keys match option_type values directly (e.g. enchant_effects).
 */
export const LISTING_SCHEMA = {
  listing: {
    relation: 'root',
    columns: {
      name: 'string',
      price: 'number',
      item_type: 'string',
      item_grade: 'string',
      erg_grade: 'string',
      erg_level: 'number',
      special_upgrade_type: 'string',
      special_upgrade_level: 'number',
      damage: 'number',
      magic_damage: 'number',
      additional_damage: 'number',
      balance: 'number',
      defense: 'number',
      protection: 'number',
      magic_defense: 'number',
      magic_protection: 'number',
      durability: 'number',
      piercing_level: 'number',
    },
  },
  prefix_enchant: {
    relation: 'belongs_to',
    columns: {
      name: 'string',
      rank: 'number',
    },
  },
  suffix_enchant: {
    relation: 'belongs_to',
    columns: {
      name: 'string',
      rank: 'number',
    },
  },
  enchant_effects: {
    relation: 'has_many',
    columns: {
      option_name: 'string',
      rolled_value: 'number',
      max_level: 'number',
    },
  },
  reforge_options: {
    relation: 'has_many',
    columns: {
      option_name: 'string',
      rolled_value: 'number',
      max_level: 'number',
    },
  },
  echostone_options: {
    relation: 'has_many',
    columns: {
      option_name: 'string',
      rolled_value: 'number',
      max_level: 'number',
    },
  },
  murias_relic_options: {
    relation: 'has_many',
    columns: {
      option_name: 'string',
      rolled_value: 'number',
      max_level: 'number',
    },
  },
  game_item: {
    relation: 'belongs_to',
    columns: {
      name: 'string',
      type: 'string',
    },
  },
};

export const COMPARE_OPS = ['==', '!=', '>=', '<=', '>', '<', 'in'];
