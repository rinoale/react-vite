import { findGameItemByName } from './gameItems';

/**
 * Parse the examine-item API response into form-ready data.
 *
 * Pure function — no React state, no side effects.
 *
 * @param {Object} data - Response from POST /examine-item
 * @returns {{ itemName: string, description: string, sections: Object,
 *             sessionId: string|null, parsedItemName: string,
 *             gameItemMatch: Object|null, allLines: Array }}
 */
export function parseExamineResult(data) {
  const sections = data.sections || {};
  const allLines = data.all_lines || [];
  const sessionId = data.session_id || null;

  const parsedItemName = sections.pre_header?.parsed_item_name?.item_name || '';
  const itemName = parsedItemName || sections.item_name?.text || '';
  const description = allLines.map(l => l.text).join('\n');

  // Resolve game item from parsed name (local config lookup)
  const gameItemMatch = parsedItemName ? findGameItemByName(parsedItemName) : null;

  return {
    itemName,
    description,
    sections,
    sessionId,
    parsedItemName,
    gameItemMatch,
    allLines,
  };
}
