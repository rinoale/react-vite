import React, { useEffect, useState, useCallback } from 'react';
import { Loader2, RefreshCw, Check, Image, Pencil, X, Save, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { getCorrections, approveCorrection, editCorrection, truncateCorrections } from '@mabi/shared/api/admin';

const CorrectionsPanel = () => {
  const { t } = useTranslation();
  const [corrections, setCorrections] = useState([]);
  const [status, setStatus] = useState('pending');
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ limit: 50, offset: 0 });
  const [approvingIds, setApprovingIds] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [truncating, setTruncating] = useState(false);

  const fetchCorrections = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await getCorrections({ status, limit: pagination.limit, offset: pagination.offset });
      setCorrections(data);
    } catch (error) {
      console.error('Error fetching corrections:', error);
      setCorrections([]);
    } finally {
      setIsLoading(false);
    }
  }, [status, pagination.offset, pagination.limit]);

  useEffect(() => { fetchCorrections(); }, [fetchCorrections]);

  const handleApprove = async (id) => {
    setApprovingIds((prev) => ({ ...prev, [id]: true }));
    try {
      await approveCorrection(id);
      setCorrections((prev) => prev.filter((c) => c.id !== id));
    } catch (error) {
      console.error('Error approving correction:', error);
    } finally {
      setApprovingIds((prev) => ({ ...prev, [id]: false }));
    }
  };

  const startEdit = (c) => { setEditingId(c.id); setEditText(c.corrected_text); };
  const cancelEdit = () => { setEditingId(null); setEditText(''); };

  const saveEdit = async (id) => {
    setSavingEdit(true);
    try {
      await editCorrection(id, editText);
      setCorrections((prev) => prev.map((c) => (c.id === id ? { ...c, corrected_text: editText } : c)));
      setEditingId(null);
    } catch (error) {
      console.error('Error editing correction:', error);
    } finally {
      setSavingEdit(false);
    }
  };

  const handleTruncate = async () => {
    if (!window.confirm(t('corrections.truncateConfirm'))) return;
    setTruncating(true);
    try {
      await truncateCorrections();
      setCorrections([]);
      setPagination((p) => ({ ...p, offset: 0 }));
    } catch (error) {
      console.error('Error truncating corrections:', error);
    } finally {
      setTruncating(false);
    }
  };

  const cropUrl = (c) => `/api/admin/corrections/crop/${c.session_id}/${c.image_filename}`;

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl overflow-hidden">
      <div className="bg-gray-700/50 px-6 py-4 flex justify-between items-center">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Image className="w-5 h-5 text-cyan-500" />
          {t('corrections.title')}
        </h2>
        <div className="flex items-center gap-4">
          <div className="flex rounded overflow-hidden border border-gray-600">
            {['pending', 'approved'].map((s) => (
              <button
                key={s}
                onClick={() => { setStatus(s); setPagination((p) => ({ ...p, offset: 0 })); }}
                className={`text-xs px-3 py-1 uppercase font-bold ${
                  status === s ? 'bg-cyan-600 text-white' : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                }`}
              >
                {t(`corrections.${s}`)}
              </button>
            ))}
          </div>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={pagination.offset === 0}
          >
            {t('corrections.prev')}
          </button>
          <span className="text-xs font-mono">
            {pagination.offset + 1} - {pagination.offset + corrections.length}
          </span>
          <button
            onClick={() => setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))}
            className="text-xs bg-gray-600 hover:bg-gray-500 px-3 py-1 rounded"
            disabled={corrections.length < pagination.limit}
          >
            {t('corrections.next')}
          </button>
          <button onClick={fetchCorrections} className="p-1 hover:text-cyan-400" title={t('corrections.refresh')}>
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={handleTruncate} disabled={truncating} className="p-1 hover:text-red-400 text-gray-500 disabled:opacity-50" title={t('corrections.truncate')}>
            <Trash2 className={`w-4 h-4 ${truncating ? 'animate-pulse' : ''}`} />
          </button>
        </div>
      </div>

      <div className="divide-y divide-gray-700">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
          </div>
        ) : corrections.length === 0 ? (
          <div className="px-6 py-8 text-center text-xs text-gray-500 uppercase tracking-wide">
            {t('corrections.noCorrections', { status })}
          </div>
        ) : corrections.map((c) => (
          <div key={c.id} className="px-6 py-4 flex items-start gap-6 hover:bg-gray-700/30 transition-colors">
            <div className="flex-shrink-0 bg-black rounded border border-gray-600 overflow-hidden">
              <img src={cropUrl(c)} alt={`Line ${c.line_index}`} className="h-8 min-w-[60px] max-w-[400px] object-contain" style={{ imageRendering: 'pixelated' }} />
            </div>
            <div className="flex-1 min-w-0 space-y-1">
              {editingId === c.id ? (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500 line-through">{c.original_text}</span>
                  <span className="text-gray-600">&rarr;</span>
                  <input
                    type="text" value={editText} onChange={(e) => setEditText(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') saveEdit(c.id); if (e.key === 'Escape') cancelEdit(); }}
                    autoFocus className="flex-1 text-sm bg-gray-900 border border-cyan-600 rounded px-2 py-0.5 text-green-400 outline-none"
                  />
                </div>
              ) : (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm text-gray-500 line-through">{c.original_text}</span>
                  <span className="text-gray-600">&rarr;</span>
                  <span className="text-sm text-green-400 font-medium">{c.corrected_text}</span>
                </div>
              )}
              <div className="flex items-center gap-3 flex-wrap">
                {c.section && <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300">{c.section}</span>}
                {c.ocr_model && <span className="text-[10px] font-mono text-gray-500 bg-black/30 px-1.5 py-0.5 rounded">{c.ocr_model}</span>}
                {c.confidence != null && <span className="text-[10px] text-gray-500">{(Number(c.confidence) * 100).toFixed(1)}%</span>}
                {c.fm_applied && <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-yellow-900/40 text-yellow-300">FM</span>}
                {c.charset_mismatch && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-900/40 text-red-300" title={`Missing chars: ${c.charset_mismatch}`}>CHARSET: {c.charset_mismatch}</span>}
                {c.is_stitched && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-orange-900/40 text-orange-300" title="Crop is stitched from multiple lines">STITCHED</span>}
                <span className="text-[10px] font-mono text-gray-600">ID: {c.id}</span>
                {c.created_at && <span className="text-[10px] text-gray-600">{new Date(c.created_at).toLocaleString()}</span>}
              </div>
            </div>
            {status === 'pending' && (
              <div className="flex-shrink-0 flex items-center gap-2">
                {editingId === c.id ? (
                  <>
                    <button onClick={() => saveEdit(c.id)} disabled={savingEdit} className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-cyan-700 hover:bg-cyan-600 text-white disabled:opacity-50">
                      {savingEdit ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />} {t('corrections.save')}
                    </button>
                    <button onClick={cancelEdit} className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-gray-600 hover:bg-gray-500 text-white">
                      <X className="w-3 h-3" />
                    </button>
                  </>
                ) : (
                  <>
                    <button onClick={() => startEdit(c)} className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-gray-600 hover:bg-gray-500 text-white">
                      <Pencil className="w-3 h-3" />
                    </button>
                    <button onClick={() => handleApprove(c.id)} disabled={approvingIds[c.id]} className="flex items-center gap-1 text-xs font-bold uppercase px-3 py-1.5 rounded bg-green-700 hover:bg-green-600 text-white disabled:opacity-50">
                      {approvingIds[c.id] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />} {t('corrections.approve')}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default CorrectionsPanel;
