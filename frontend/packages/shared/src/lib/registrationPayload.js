/**
 * Build the registration payload from form state.
 *
 * Collects all OCR lines, resolves enchant effect IDs from config,
 * extracts structured reforge/erg data.
 *
 * @param {Object} params
 * @param {string} params.sessionId
 * @param {string} params.name
 * @param {string} params.price
 * @param {string} params.category
 * @param {Object|null} params.gameItem - selected game item
 * @param {Object} params.sections - form sections data
 * @returns {Object} payload ready for POST /register-listing
 */
export function buildRegistrationPayload({ sessionId, name, price, category, gameItem, sections }) {
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

  const enchants = buildEnchantPayload(sections.enchant);
  const reforge_options = buildReforgePayload(sections.reforge);
  const { itemType, itemGrade, ergGrade, ergLevel } = extractAttributes(sections);

  return {
    session_id: sessionId,
    name,
    price,
    category,
    game_item_id: gameItem?.id || null,
    item_type: itemType,
    item_grade: itemGrade,
    erg_grade: ergGrade,
    erg_level: ergLevel,
    special_upgrade_type: sections?.item_mod?.special_upgrade_type || null,
    special_upgrade_level: sections?.item_mod?.special_upgrade_level || null,
    lines,
    enchants,
    reforge_options,
  };
}

/** Resolve enchant effects against window.ENCHANTS_CONFIG */
function buildEnchantPayload(enchantSec) {
  const enchants = [];
  if (!enchantSec) return enchants;

  const resolveEffects = (slotData, slotInt) => {
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
    return (slotData.effects || []).map(eff => {
      if (eff.enchant_effect_id) return eff;
      const configEff = findConfigEff(eff.option_name);
      return {
        text: eff.text,
        option_name: configEff?.option_name ?? eff.option_name ?? null,
        option_level: eff.option_level ?? null,
        enchant_effect_id: configEff?.enchant_effect_id ?? null,
      };
    });
  };

  if (enchantSec.prefix?.name) {
    enchants.push({
      slot: 0,
      name: enchantSec.prefix.name,
      rank: enchantSec.prefix.rank || '',
      effects: resolveEffects(enchantSec.prefix, 0),
    });
  }
  if (enchantSec.suffix?.name) {
    enchants.push({
      slot: 1,
      name: enchantSec.suffix.name,
      rank: enchantSec.suffix.rank || '',
      effects: resolveEffects(enchantSec.suffix, 1),
    });
  }
  return enchants;
}

/** Extract structured reforge options */
function buildReforgePayload(reforgeSec) {
  if (!reforgeSec?.options) return [];
  return reforgeSec.options.map(opt => ({
    name: opt.option_name || opt.name || '',
    reforge_option_id: opt.reforge_option_id ?? null,
    level: opt.option_level ?? opt.level ?? null,
    max_level: opt.max_level ?? null,
  }));
}

/** Extract item type, grade, erg from sections */
function extractAttributes(sections) {
  const itemType = sections?.item_type?.text || null;
  const itemGrade = sections?.item_grade?.text || null;

  let ergGrade = null;
  let ergLevel = null;
  const ergSection = sections?.erg;
  if (ergSection?.lines?.length) {
    const ergText = ergSection.lines.map(l => l.text).join(' ');
    const gradeMatch = ergText.match(/\b([SABCDEF])\b/);
    if (gradeMatch) ergGrade = gradeMatch[1];
    const levelMatch = ergText.match(/(\d+)/);
    if (levelMatch) ergLevel = parseInt(levelMatch[1], 10);
  }

  return { itemType, itemGrade, ergGrade, ergLevel };
}
