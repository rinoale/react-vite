import { findGameItemByName } from './gameItems';

/**
 * Collect all line texts from sections in order.
 */
function collectLinesFromSections(sections) {
  const lines = [];
  for (const sec of Object.values(sections)) {
    if (sec.header_text) lines.push(sec.header_text);
    if (sec.lines) {
      for (const l of sec.lines) {
        if (l.text) lines.push(l.text);
      }
    }
  }
  return lines;
}

/**
 * Parse the examine-item API response into form-ready data.
 *
 * Pure function — no React state, no side effects.
 *
 * @param {Object} data - Response from POST /examine-item
 * @returns {{ itemName: string, description: string, sections: Object,
 *             sessionId: string|null, parsedItemName: string,
 *             gameItemMatch: Object|null }}
 */
export function parseExamineResult(data) {
  const sections = data.sections || {};
  const sessionId = data.session_id || null;

  const parsedItemName = sections.pre_header?.item_name || '';
  const itemName = parsedItemName || sections.item_name?.text || '';
  const description = collectLinesFromSections(sections).join('\n');

  // Resolve game item from parsed name (local config lookup)
  const gameItemMatch = parsedItemName ? findGameItemByName(parsedItemName) : null;

  return {
    itemName,
    description,
    sections,
    sessionId,
    parsedItemName,
    gameItemMatch,
    abbreviated: data.abbreviated ?? true,
  };
}
