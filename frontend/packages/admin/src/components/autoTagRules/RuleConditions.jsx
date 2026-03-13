import { useTranslation } from 'react-i18next';
import { Plus, X } from 'lucide-react';
import { LISTING_SCHEMA, COMPARE_OPS } from './ruleSchema';

const sel = 'bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 outline-none focus:border-cyan-500';
const inp = 'bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-gray-300 outline-none focus:border-cyan-500';
const btnAdd = 'text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 mt-2';
const btnToggle = 'text-xs px-1.5 py-0.5 rounded border shrink-0';
const btnToggleOn = `${btnToggle} bg-cyan-900/50 text-cyan-400 border-cyan-700/50`;
const btnToggleOff = `${btnToggle} bg-gray-800 text-gray-500 border-gray-700 hover:text-gray-400`;

const TABLE_KEYS = Object.keys(LISTING_SCHEMA);

const isColRef = (v) => v !== null && typeof v === 'object' && 'table' in v && 'column' in v;

const emptyCondition = () => ({ table: '', column: '', op: '==', value: '', refer: '' });

const RuleConditions = ({ conditions, onChange, readOnly }) => {
  const { t } = useTranslation();

  const tTable = (key) => t(`autoTagRules.schema.tables.${key}`, key);
  const tColumn = (key) => t(`autoTagRules.schema.columns.${key}`, key);

  const formatValue = (v) => {
    if (v === null) return 'null';
    if (isColRef(v)) return `${tTable(v.table)}.${tColumn(v.column)}`;
    if (Array.isArray(v)) return `[${v.join(', ')}]`;
    return String(v);
  };

  const set = (idx, patch) => {
    onChange(conditions.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  };

  const remove = (idx) => {
    onChange(conditions.filter((_, i) => i !== idx));
  };

  const add = () => {
    onChange([...conditions, { ...emptyCondition(), logic: 'AND' }]);
  };

  const toggleNull = (idx) => {
    const c = conditions[idx];
    set(idx, { value: c.value === null ? '' : null });
  };

  const toggleColRef = (idx) => {
    const c = conditions[idx];
    if (isColRef(c.value)) {
      set(idx, { value: '' });
    } else {
      const isPlural = LISTING_SCHEMA[c.table]?.relation === 'has_many';
      set(idx, { value: { table: isPlural ? c.table : '', column: '' } });
    }
  };

  const parseValue = (raw) => {
    if (raw === '') return '';
    const num = Number(raw);
    return Number.isFinite(num) ? num : raw;
  };

  if (readOnly) {
    return (
      <div className="space-y-1">
        {conditions.map((c, i) => {
          const valIsRef = isColRef(c.value);
          return (
            <div key={i} className="flex items-center gap-2 text-sm flex-wrap">
              {i > 0 && <span className="text-cyan-500 font-bold text-xs w-8">{c.logic}</span>}
              <span className="font-mono text-gray-400">{tTable(c.table)}</span>
              <span className="text-gray-600">.</span>
              <span className="font-mono text-cyan-400">{tColumn(c.column)}</span>
              <span className="text-gray-400">{c.op}</span>
              <span className={`font-mono ${valIsRef ? 'text-cyan-400' : 'text-gray-300'}`}>
                {formatValue(c.value)}
              </span>
              {c.refer && (
                <>
                  <span className="text-gray-600 ml-2">as</span>
                  <span className="font-mono text-amber-300">{`{${c.refer}}`}</span>
                </>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {conditions.map((c, idx) => {
        const columns = LISTING_SCHEMA[c.table]?.columns || {};
        const columnKeys = Object.keys(columns);
        const isNull = c.value === null;
        const valIsRef = isColRef(c.value);
        const isPluralTable = LISTING_SCHEMA[c.table]?.relation === 'has_many';
        // For has_many, col ref is always same table; for singular, allow other singulars
        const refTable = valIsRef ? c.value.table : '';
        const refColumns = Object.keys(LISTING_SCHEMA[refTable]?.columns || {});
        const refTableKeys = isPluralTable
          ? []
          : TABLE_KEYS.filter((k) => LISTING_SCHEMA[k].relation !== 'has_many');

        return (
          <div key={idx} className="flex items-center gap-2 flex-wrap">
            {/* AND/OR */}
            {idx > 0 && (
              <select
                className={`${sel} w-16 text-xs font-bold text-cyan-400`}
                value={c.logic || 'AND'}
                onChange={(e) => set(idx, { logic: e.target.value })}
              >
                <option value="AND">AND</option>
                <option value="OR">OR</option>
              </select>
            )}
            {idx === 0 && <span className="w-16" />}

            {/* table */}
            <select className={sel} value={c.table} onChange={(e) => set(idx, { table: e.target.value, column: '' })}>
              <option value="">--</option>
              {TABLE_KEYS.map((k) => <option key={k} value={k}>{tTable(k)}</option>)}
            </select>

            <span className="text-gray-600">.</span>

            {/* column */}
            <select className={sel} value={c.column} onChange={(e) => set(idx, { column: e.target.value })}>
              <option value="">--</option>
              {columnKeys.map((k) => <option key={k} value={k}>{tColumn(k)}</option>)}
            </select>

            {/* operator */}
            <select className={`${sel} w-16`} value={c.op} onChange={(e) => {
              const newOp = e.target.value;
              const patch = { op: newOp };
              if (newOp === 'in' && !Array.isArray(c.value)) patch.value = [];
              if (newOp !== 'in' && Array.isArray(c.value)) patch.value = '';
              set(idx, patch);
            }}>
              {COMPARE_OPS.map((op) => <option key={op} value={op}>{op}</option>)}
            </select>

            {/* value */}
            {isNull ? (
              <span className="text-xs font-mono text-gray-500 w-24 text-center">null</span>
            ) : c.op === 'in' ? (
              <input
                className={`${inp} w-36`}
                value={Array.isArray(c.value) ? c.value.join(', ') : (c.value ?? '')}
                onChange={(e) => {
                  const arr = e.target.value.split(',').map((s) => {
                    const trimmed = s.trim();
                    const num = Number(trimmed);
                    return trimmed === '' ? '' : Number.isFinite(num) ? num : trimmed;
                  }).filter((v) => v !== '');
                  set(idx, { value: arr });
                }}
                placeholder="a, b, c"
              />
            ) : valIsRef ? (
              <div className="flex items-center gap-1">
                {isPluralTable ? (
                  <span className="text-xs font-mono text-gray-500">{tTable(c.table)}.</span>
                ) : (
                  <>
                    <select
                      className={sel}
                      value={c.value.table}
                      onChange={(e) => set(idx, { value: { table: e.target.value, column: '' } })}
                    >
                      <option value="">--</option>
                      {refTableKeys.map((k) => <option key={k} value={k}>{tTable(k)}</option>)}
                    </select>
                    <span className="text-gray-600">.</span>
                  </>
                )}
                <select
                  className={sel}
                  value={c.value.column}
                  onChange={(e) => set(idx, { value: { ...c.value, column: e.target.value } })}
                >
                  <option value="">--</option>
                  {refColumns.map((k) => <option key={k} value={k}>{tColumn(k)}</option>)}
                </select>
              </div>
            ) : (
              <input
                className={`${inp} w-24`}
                value={c.value ?? ''}
                onChange={(e) => set(idx, { value: parseValue(e.target.value) })}
                placeholder={t('autoTagRules.builder.value')}
              />
            )}

            {/* null toggle */}
            <label className="flex items-center gap-1 text-xs text-gray-500 cursor-pointer shrink-0">
              <input type="checkbox" checked={isNull} onChange={() => toggleNull(idx)} className="accent-cyan-500" />
              null
            </label>

            {/* column ref toggle */}
            {!isNull && c.op !== 'in' && (
              <button
                className={valIsRef ? btnToggleOn : btnToggleOff}
                onClick={() => toggleColRef(idx)}
                title={valIsRef ? t('autoTagRules.builder.switchLiteral') : t('autoTagRules.builder.switchColumn')}
              >
                col
              </button>
            )}

            {/* refer name */}
            <input
              className={`${inp} w-24`}
              value={c.refer || ''}
              onChange={(e) => set(idx, { refer: e.target.value })}
              placeholder="refer"
            />

            {/* remove */}
            <button className="text-gray-500 hover:text-red-400 shrink-0" onClick={() => remove(idx)}>
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      })}

      <button className={btnAdd} onClick={add}>
        <Plus className="w-3 h-3" /> {t('autoTagRules.builder.addCondition')}
      </button>
    </div>
  );
};

export default RuleConditions;
