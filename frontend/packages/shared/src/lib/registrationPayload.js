/**
 * Build the registration payload from form state.
 *
 * Collects all OCR lines, resolves enchant/reforge IDs from config,
 * and produces unified listing_options[].
 *
 * @param {Object} params
 * @param {string} params.sessionId
 * @param {string} params.name
 * @param {string} params.description
 * @param {string} params.price
 * @param {string} params.category
 * @param {Object|null} params.gameItem - selected game item
 * @param {Object} params.sections - form sections data
 * @param {string[]} params.tags - user-assigned tags (max 3)
 * @returns {Object} payload ready for POST /register-listing
 */
export function buildRegistrationPayload({ sessionId, name, description, price, category, gameItem, sections, tags }) {
  // Collect all lines with (section, line_index) + current text
  const lines = [];
  for (const [secKey, secData] of Object.entries(sections)) {
    if (!secData.lines) continue;
    for (const line of secData.lines) {
      if (line.line_index != null) {
        lines.push({ section: secKey, line_index: line.line_index, text: line.text });
      }
    }
  }

  const enchants = buildEnchantSlots(sections.enchant);
  const listing_options = [
    ...buildEnchantEffectOptions(sections.enchant),
    ...buildReforgeOptions(sections.reforge),
    ...buildEchostoneOptions(sections._echostone_options),
    ...buildMuriasRelicOptions(sections._murias_relic_options),
  ];
  const { itemType, itemGrade, ergGrade, ergLevel } = extractAttributes(sections);

  return {
    session_id: sessionId,
    name,
    description: description || null,
    price,
    category,
    game_item_id: gameItem?.id || null,
    item_type: itemType,
    item_grade: itemGrade,
    erg_grade: ergGrade,
    erg_level: ergLevel,
    special_upgrade_type: sections?.item_mod?.special_upgrade_type || null,
    special_upgrade_level: sections?.item_mod?.special_upgrade_level || null,
    attrs: sections?.item_attrs?.attrs || null,
    lines,
    enchants,
    listing_options,
    tags: (tags || []).slice(0, 3),
  };
}

/** Build enchant slots (slot/name/rank only, no effects) */
function buildEnchantSlots(enchantSec) {
  const enchants = [];
  if (!enchantSec) return enchants;
  if (enchantSec.prefix?.name) {
    enchants.push({ slot: 0, name: enchantSec.prefix.name, rank: enchantSec.prefix.rank || '' });
  }
  if (enchantSec.suffix?.name) {
    enchants.push({ slot: 1, name: enchantSec.suffix.name, rank: enchantSec.suffix.rank || '' });
  }
  return enchants;
}

/** Resolve enchant effects into listing_options with option_type='enchant_effects' */
function buildEnchantEffectOptions(enchantSec) {
  if (!enchantSec) return [];
  const options = [];

  const resolveSlot = (slotData, slotInt) => {
    if (!slotData?.name) return;
    const config = (window.ENCHANTS_CONFIG || []).find(
      e => e.name === slotData.name && e.slot === slotInt
    );
    const usedIdx = new Set();
    const findConfigEff = (ocrName) => {
      if (!config?.effects || !ocrName) return null;
      let idx = config.effects.findIndex(
        (ce, i) => !usedIdx.has(i) && ce.option_name === ocrName
      );
      if (idx < 0) {
        const candidates = config.effects
          .map((ce, i) => ({ ce, i }))
          .filter(({ ce, i }) => !usedIdx.has(i) && ce.option_name && ocrName.includes(ce.option_name))
          .sort((a, b) => b.ce.option_name.length - a.ce.option_name.length);
        if (candidates.length) idx = candidates[0].i;
      }
      if (idx >= 0) { usedIdx.add(idx); return config.effects[idx]; }
      return null;
    };

    for (const eff of slotData.effects || []) {
      const configEff = findConfigEff(eff.option_name);
      const effIdx = configEff ? config.effects.indexOf(configEff) : -1;
      options.push({
        option_type: 'enchant_effects',
        option_name: configEff?.option_name ?? eff.option_name ?? '',
        enchant_id: config?.id || null,
        effect_order: effIdx >= 0 ? effIdx : null,
        rolled_value: eff.option_level ?? null,
      });
    }
  };

  resolveSlot(enchantSec.prefix, 0);
  resolveSlot(enchantSec.suffix, 1);
  return options;
}

/** Convert reforge options into listing_options with option_type='reforge_options' */
function buildReforgeOptions(reforgeSec) {
  if (!reforgeSec?.options) return [];
  return reforgeSec.options.map(opt => ({
    option_type: 'reforge_options',
    option_name: opt.option_name || opt.name || '',
    option_id: opt.reforge_option_id ?? null,
    rolled_value: opt.option_level ?? opt.level ?? null,
    max_level: opt.max_level ?? null,
  }));
}

/** Convert echostone options into listing_options with option_type='echostone_options' */
function buildEchostoneOptions(opts) {
  if (!opts?.length) return [];
  return opts.map(opt => ({
    option_type: 'echostone_options',
    option_name: opt.option_name || '',
    option_id: opt.option_id ?? null,
    rolled_value: opt.level ?? null,
    max_level: opt.max_level ?? null,
  }));
}

/** Convert murias relic options into listing_options with option_type='murias_relic_options' */
function buildMuriasRelicOptions(opts) {
  if (!opts?.length) return [];
  return opts.map(opt => ({
    option_type: 'murias_relic_options',
    option_name: opt.option_name || '',
    option_id: opt.option_id ?? null,
    rolled_value: opt.level ?? null,
    max_level: opt.max_level ?? null,
  }));
}

/** Extract item type, grade, erg from sections */
function extractAttributes(sections) {
  const itemType = sections?.item_type?.text || null;
  const itemGrade = sections?.item_grade?.text || null;

  const ergGrade = sections?.erg?.erg_grade || null;
  const ergLevel = sections?.erg?.erg_level || null;

  return { itemType, itemGrade, ergGrade, ergLevel };
}
