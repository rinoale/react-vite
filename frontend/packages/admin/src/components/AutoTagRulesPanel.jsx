import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, RefreshCw, Zap, Plus, Trash2, ChevronDown, ChevronRight, Power, PowerOff } from 'lucide-react';
import {
  getAutoTagRules, createAutoTagRule, updateAutoTagRule, deleteAutoTagRule,
} from '@mabi/shared/api/admin';
import {
  panelOuter, panelHeader, panelTitle, loadingCenter, loadingIcon,
  hoverRow, btnPagGray,
} from '@mabi/shared/styles';
import { getRuleSummary } from './autoTagRules/ruleSummary';
import RuleForm from './autoTagRules/RuleForm';
import RuleConditions from './autoTagRules/RuleConditions';

const emptyForm = () => ({
  name: '', description: '', priority: 0,
  config: { conditions: [], tag_template: '' }, enabled: true,
});

const tagBadge = 'inline-block text-xs px-2 py-0.5 rounded bg-amber-900/50 text-amber-300 border border-amber-700/50';

const AutoTagRulesPanel = () => {
  const { t } = useTranslation();
  const [rules, setRules] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState(emptyForm);
  const [editId, setEditId] = useState(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await getAutoTagRules({ limit: 500, offset: 0 });
      setRules(res.data.rows || []);
    } catch (err) {
      console.error('Error fetching auto tag rules:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleToggle = useCallback(async (rule) => {
    try {
      await updateAutoTagRule(rule.id, { enabled: !rule.enabled });
      setRules((prev) => prev.map((r) => r.id === rule.id ? { ...r, enabled: !r.enabled } : r));
    } catch (err) {
      console.error('Error toggling rule:', err);
    }
  }, []);

  const handleDelete = useCallback(async (rule) => {
    if (!confirm(t('autoTagRules.deleteConfirm', { name: rule.name }))) return;
    try {
      await deleteAutoTagRule(rule.id);
      setRules((prev) => prev.filter((r) => r.id !== rule.id));
      if (expandedId === rule.id) setExpandedId(null);
    } catch (err) {
      console.error('Error deleting rule:', err);
    }
  }, [expandedId, t]);

  const startEdit = useCallback((rule) => {
    setEditId(rule.id);
    setForm({
      name: rule.name,
      description: rule.description || '',
      priority: rule.priority,
      config: rule.config || { conditions: [], tag_template: '' },
      enabled: rule.enabled,
    });
    setExpandedId(rule.id);
    setShowCreate(false);
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const sortedConditions = [...(form.config.conditions || [])].sort((a, b) => (a.group ?? Infinity) - (b.group ?? Infinity));
      const config = { ...form.config, conditions: sortedConditions };
      const payload = { ...form, config, priority: Number(form.priority), rule_type: 'condition' };
      if (editId) {
        const res = await updateAutoTagRule(editId, payload);
        setRules((prev) => prev.map((r) => r.id === editId ? res.data : r));
        setEditId(null);
      } else {
        const res = await createAutoTagRule(payload);
        setRules((prev) => [...prev, res.data]);
        setShowCreate(false);
      }
      setForm(emptyForm());
      setExpandedId(null);
    } catch (err) {
      console.error('Error saving rule:', err);
    } finally {
      setSaving(false);
    }
  }, [form, editId]);

  const handleCancel = useCallback(() => {
    setEditId(null);
    setShowCreate(false);
    setForm(emptyForm());
  }, []);

  if (isLoading && rules.length === 0) {
    return (
      <div className={loadingCenter}>
        <Loader2 className={loadingIcon} />
      </div>
    );
  }

  return (
    <div className={panelOuter}>
      {/* header */}
      <div className={panelHeader}>
        <h2 className={`${panelTitle} flex items-center gap-2`}>
          <Zap className="w-5 h-5 text-amber-500" />
          {t('autoTagRules.title')}
          <span className="text-sm font-mono text-gray-500 ml-2">{rules.length}</span>
        </h2>
        <div className="flex items-center gap-2">
          <button className={btnPagGray} onClick={() => { setShowCreate(true); setEditId(null); setForm(emptyForm()); }}>
            <Plus className="w-3 h-3 inline mr-1" />{t('autoTagRules.add')}
          </button>
          <button onClick={fetchData} className="p-1 hover:text-cyan-400" title={t('autoTagRules.refresh')}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* create form */}
      {showCreate && !editId && (
        <RuleForm
          form={form}
          setForm={setForm}
          onSave={handleSave}
          onCancel={handleCancel}
          saving={saving}
          editId={null}
        />
      )}

      {/* rule list */}
      <div className="divide-y divide-gray-700/50">
        {rules.map((rule) => {
          const isExpanded = expandedId === rule.id;
          const isEditing = editId === rule.id;
          const config = rule.config || {};
          return (
            <div key={rule.id}>
              {/* row */}
              <div
                className={`${hoverRow} flex items-center cursor-pointer px-6 py-3`}
                onClick={() => setExpandedId(isExpanded ? null : rule.id)}
              >
                <div className="w-6 shrink-0">
                  {isExpanded
                    ? <ChevronDown className="w-3 h-3 text-gray-500" />
                    : <ChevronRight className="w-3 h-3 text-gray-500" />}
                </div>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-200">{rule.name}</span>
                  <span className="ml-3 text-xs text-gray-500">{getRuleSummary(rule)}</span>
                </div>
                <span className="text-xs font-mono text-gray-400 w-8 text-center shrink-0">{rule.priority}</span>
                <button
                  className="p-1 mx-2 shrink-0"
                  onClick={(e) => { e.stopPropagation(); handleToggle(rule); }}
                  title={rule.enabled ? t('autoTagRules.disable') : t('autoTagRules.enable')}
                >
                  {rule.enabled
                    ? <Power className="w-4 h-4 text-green-400" />
                    : <PowerOff className="w-4 h-4 text-gray-600" />}
                </button>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    className="text-xs text-cyan-400 hover:text-cyan-300 px-2 py-0.5"
                    onClick={(e) => { e.stopPropagation(); startEdit(rule); }}
                  >
                    {t('autoTagRules.edit')}
                  </button>
                  <button
                    className="text-xs text-red-400 hover:text-red-300 px-2 py-0.5"
                    onClick={(e) => { e.stopPropagation(); handleDelete(rule); }}
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>

              {/* expanded detail / edit form */}
              {isExpanded && (
                isEditing ? (
                  <RuleForm
                    form={form}
                    setForm={setForm}
                    onSave={handleSave}
                    onCancel={handleCancel}
                    saving={saving}
                    editId={editId}
                  />
                ) : (
                  <div className="px-6 py-3 bg-gray-900/30 border-t border-gray-700/50 space-y-2">
                    <RuleConditions conditions={config.conditions || []} readOnly />
                    {config.tag_template && (
                      <div className="flex items-center gap-2 pt-1">
                        <span className="text-xs text-gray-500">→ tag:</span>
                        <span className={tagBadge}>{config.tag_template}</span>
                      </div>
                    )}
                  </div>
                )
              )}
            </div>
          );
        })}
        {rules.length === 0 && (
          <p className="text-center text-gray-500 py-8">{t('autoTagRules.noRules')}</p>
        )}
      </div>
    </div>
  );
};

export default AutoTagRulesPanel;
