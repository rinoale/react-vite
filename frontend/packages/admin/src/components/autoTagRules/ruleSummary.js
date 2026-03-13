/** Generate human-readable one-liner from a rule's config. */

function formatCondition(c) {
  const val = c.value === null || c.value === undefined ? 'null' : String(c.value);
  const group = c.group != null ? `[G${c.group}] ` : '';
  return `${group}${c.table}.${c.column} ${c.op} ${val}`;
}

export function getRuleSummary(rule) {
  const config = rule.config;
  if (!config) return '';

  const conditions = config.conditions || [];
  const tag = config.tag_template || '?';

  if (conditions.length === 0) return `→ tag: ${tag}`;

  const parts = conditions.map((c, i) => {
    const prefix = i > 0 ? ` ${c.logic || 'AND'} ` : '';
    return `${prefix}${formatCondition(c)}`;
  });

  return `${parts.join('')} → tag: ${tag}`;
}
