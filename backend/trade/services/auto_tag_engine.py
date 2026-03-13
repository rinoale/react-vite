"""Database-driven auto-tag rule engine.

Evaluates auto_tag_rules against a listing payload to produce tag names.

Every rule is a list of conditions + tag template.
Each condition specifies table.column, operator, and value (literal or column ref).
"""
import re
from sqlalchemy.orm import Session

from db.models import AutoTagRule, GameItem
from lib.utils.log import logger


_SINGULAR_TABLES = {'listing', 'prefix_enchant', 'suffix_enchant', 'game_item'}
_PLURAL_TABLES = {'enchant_effects', 'reforge_options', 'echostone_options', 'murias_relic_options'}


def evaluate_rules(payload, db: Session) -> list[str]:
    """Load enabled rules and evaluate against payload. Returns tag names."""
    rules = (
        db.query(AutoTagRule)
        .filter(AutoTagRule.enabled.is_(True))
        .order_by(AutoTagRule.priority, AutoTagRule.id)
        .all()
    )
    tags: list[str] = []
    for rule in rules:
        try:
            result = _eval_condition(payload, rule.config, db)
            tags.extend(result)
        except Exception:
            logger.exception("auto-tag  rule=%s failed", rule.name)
    return tags


def _resolve_singular(table: str, payload, db: Session):
    """Resolve a singular table reference to a single object (or None)."""
    if table == 'listing':
        return payload
    if table == 'prefix_enchant':
        for e in getattr(payload, 'enchants', []):
            if e.slot == 0:
                return e
        return None
    if table == 'suffix_enchant':
        for e in getattr(payload, 'enchants', []):
            if e.slot == 1:
                return e
        return None
    if table == 'game_item':
        gid = getattr(payload, 'game_item_id', None)
        if not gid:
            return None
        return db.query(GameItem).filter(GameItem.id == gid).first()
    return None


def _resolve_plural(table: str, payload):
    """Resolve a plural table reference to listing_options filtered by option_type.

    Schema key matches option_type directly (e.g. enchant_effects).
    """
    return [
        opt for opt in getattr(payload, 'listing_options', [])
        if getattr(opt, 'option_type', None) == table
    ]


def _get_value(obj, column):
    """Get a column value from an object."""
    return getattr(obj, column, None)


def _resolve_condition_value(cond, row_context: dict, payload, db: Session):
    """Resolve the comparison value — literal or column reference."""
    value = cond.get('value')
    if isinstance(value, dict) and 'table' in value and 'column' in value:
        ref_table = value['table']
        ref_column = value['column']
        if ref_table in row_context:
            return _get_value(row_context[ref_table], ref_column)
        obj = _resolve_singular(ref_table, payload, db)
        return _get_value(obj, ref_column) if obj else None
    return value


def _check_condition(actual, op: str, expected) -> bool:
    """Evaluate a single comparison."""
    if op == '!=' and expected is None:
        return actual is not None
    if op == '==' and expected is None:
        return actual is None
    if actual is None:
        return False
    if op in ('>=', '<=', '>', '<'):
        try:
            actual = float(actual)
            expected = float(expected)
        except (ValueError, TypeError):
            return False
    if op == '==':
        return _coerce_eq(actual, expected)
    if op == '!=':
        return not _coerce_eq(actual, expected)
    if op == '>=':
        return actual >= expected
    if op == '<=':
        return actual <= expected
    if op == '>':
        return actual > expected
    if op == '<':
        return actual < expected
    if op == 'in':
        return actual in (expected if isinstance(expected, list) else [expected])
    return False


def _coerce_eq(actual, expected):
    """Compare with type coercion for string/number mismatch."""
    if actual == expected:
        return True
    try:
        return float(actual) == float(expected)
    except (ValueError, TypeError):
        return str(actual) == str(expected)


def _render_template(template: str, refers: dict) -> str:
    """Replace {refer_name} placeholders with collected refer values."""
    def _replace(m):
        val = refers.get(m.group(1))
        return str(val) if val is not None else ''
    return re.sub(r'\{(\w+)\}', _replace, template)


def _eval_condition(payload, config: dict, db: Session) -> list[str]:
    """Unified condition evaluator.

    Conditions on plural tables (listing_option) iterate rows —
    multiple conditions on the same plural table must match the same row.
    Singular table conditions are checked once.
    """
    conditions = config.get('conditions', [])
    template = config.get('tag_template', '')
    if not conditions or not template:
        return []

    # Split conditions by table type
    singular_conds = []
    plural_groups = {}
    for cond in conditions:
        table = cond.get('table', '')
        if table in _PLURAL_TABLES:
            plural_groups.setdefault(table, []).append(cond)
        else:
            singular_conds.append(cond)

    # Check singular conditions first (left-to-right AND/OR)
    refers = {}
    row_context = {}
    result = None
    for cond in singular_conds:
        table = cond.get('table', '')
        logic = cond.get('logic', 'AND')

        if table not in row_context:
            obj = _resolve_singular(table, payload, db)
            if obj is None:
                cond_ok = False
            else:
                row_context[table] = obj

        if table in row_context:
            actual = _get_value(row_context[table], cond.get('column', ''))
            expected = _resolve_condition_value(cond, row_context, payload, db)
            cond_ok = _check_condition(actual, cond.get('op', '=='), expected)
            if cond_ok:
                refer = cond.get('refer', '')
                if refer:
                    refers[refer] = actual

        result = cond_ok if result is None else (result or cond_ok) if logic == 'OR' else (result and cond_ok)

    if result is False:
        return []

    # No plural conditions — emit tag
    if not plural_groups:
        tag = _render_template(template, refers) if '{' in template else template
        return [tag] if tag else []

    # Plural conditions — check if any condition uses group for cross-row matching
    has_groups = any(cond.get('group') is not None for cond in conditions if cond.get('table', '') in _PLURAL_TABLES)

    if has_groups:
        return _eval_plural_grouped(plural_groups, row_context, refers, template, payload, db)
    return _eval_plural_per_row(plural_groups, row_context, refers, template, payload, db)


def _eval_row(conds, item, row_context, table, payload, db):
    """Evaluate conditions against a single row with AND/OR logic. Returns (passed, refers)."""
    row_result = None
    row_refers = {}
    ctx = {**row_context, table: item}
    for cond in conds:
        logic = cond.get('logic', 'AND')
        actual = _get_value(item, cond.get('column', ''))
        expected = _resolve_condition_value(cond, ctx, payload, db)
        cond_ok = _check_condition(actual, cond.get('op', '=='), expected)
        if cond_ok:
            refer = cond.get('refer', '')
            if refer:
                row_refers[refer] = actual
        row_result = cond_ok if row_result is None else (row_result or cond_ok) if logic == 'OR' else (row_result and cond_ok)
    return bool(row_result), row_refers


def _eval_plural_per_row(plural_groups, row_context, refers, template, payload, db):
    """Legacy mode: all conditions on same table must match same row. Emits per match."""
    tags = []
    for table, conds in plural_groups.items():
        items = _resolve_plural(table, payload)
        for item in items:
            passed, row_refers = _eval_row(conds, item, row_context, table, payload, db)
            if passed:
                merged = {**refers, **row_refers}
                tag = _render_template(template, merged) if '{' in template else template
                if tag:
                    tags.append(tag)
    return tags


def _eval_plural_grouped(plural_groups, row_context, refers, template, payload, db):
    """Group mode: each condition group independently matches a row. ALL groups must pass."""
    all_refers = dict(refers)
    for table, conds in plural_groups.items():
        items = _resolve_plural(table, payload)
        # Split conditions into groups
        groups: dict[int, list] = {}
        for cond in conds:
            gid = cond.get('group', 0)
            groups.setdefault(gid, []).append(cond)

        for gid, group_conds in groups.items():
            group_passed = False
            for item in items:
                passed, row_refers = _eval_row(group_conds, item, row_context, table, payload, db)
                if passed:
                    all_refers.update(row_refers)
                    group_passed = True
                    break
            if not group_passed:
                return []

    tag = _render_template(template, all_refers) if '{' in template else template
    return [tag] if tag else []
