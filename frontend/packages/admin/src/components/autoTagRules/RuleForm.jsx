import { useTranslation } from 'react-i18next';
import RuleConditions from './RuleConditions';

const formInput = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300 outline-none focus:border-cyan-500';
const formLabel = 'text-xs font-bold text-gray-500 uppercase';
const btnSave = 'px-4 py-1.5 text-xs font-bold uppercase rounded bg-cyan-700 hover:bg-cyan-600 text-white disabled:opacity-50';
const btnCancel = 'px-4 py-1.5 text-xs font-bold uppercase rounded bg-gray-700 hover:bg-gray-600 text-gray-300';
const tagBadge = 'inline-block text-xs px-2 py-0.5 rounded bg-amber-900/50 text-amber-300 border border-amber-700/50';

const RuleForm = ({ form, setForm, onSave, onCancel, saving, editId }) => {
  const { t } = useTranslation();

  const config = form.config || {};
  const conditions = config.conditions || [];
  const tagTemplate = config.tag_template || '';

  const updateConfig = (patch) => {
    setForm((f) => ({ ...f, config: { ...f.config, ...patch } }));
  };

  return (
    <div className="px-6 py-4 bg-gray-900/50 border-b border-gray-700 space-y-3">
      {/* name + priority */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className={formLabel}>{t('autoTagRules.name')}</label>
          <input className={formInput} value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        </div>
        <div className="w-20">
          <label className={formLabel}>{t('autoTagRules.priority')}</label>
          <input type="number" className={formInput} value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))} />
        </div>
      </div>

      {/* description */}
      <div>
        <label className={formLabel}>{t('autoTagRules.description')}</label>
        <input className={formInput} value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} />
      </div>

      {/* conditions */}
      <div>
        <label className={formLabel}>{t('autoTagRules.builder.conditions')}</label>
        <div className="mt-1 p-3 border border-gray-700 rounded bg-gray-900/30">
          <RuleConditions
            conditions={conditions}
            onChange={(next) => updateConfig({ conditions: next })}
          />
        </div>
      </div>

      {/* tag template */}
      <div>
        <label className={formLabel}>{t('autoTagRules.builder.tagTemplate')}</label>
        <input
          className={formInput}
          value={tagTemplate}
          onChange={(e) => updateConfig({ tag_template: e.target.value })}
          placeholder="{refer_name}..."
        />
        {tagTemplate && (
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-gray-500">{t('autoTagRules.builder.tagOutput')}:</span>
            <span className={tagBadge}>{tagTemplate}</span>
          </div>
        )}
      </div>

      {/* actions */}
      <div className="flex gap-2 justify-end">
        <button className={btnCancel} onClick={onCancel}>{t('autoTagRules.cancel')}</button>
        <button className={btnSave} onClick={onSave} disabled={saving || !form.name}>
          {saving ? t('autoTagRules.saving') : editId ? t('autoTagRules.update') : t('autoTagRules.create')}
        </button>
      </div>
    </div>
  );
};

export default RuleForm;
