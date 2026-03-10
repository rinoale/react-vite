import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../hooks/useAuth.js';
import { updateProfile } from '../api/auth.js';
import { useToast } from './useToast.js';

const SERVERS = ['류트', '만돌린', '하프', '울프'];

const overlay = 'fixed inset-0 z-50 flex items-center justify-center bg-black/60';
const card = 'w-full max-w-sm bg-gray-800 rounded-lg border border-gray-700 p-6 shadow-xl';
const title = 'text-lg font-bold text-white mb-1';
const subtitle = 'text-sm text-gray-400 mb-5';
const label = 'block text-sm font-medium text-gray-300 mb-1';
const selectInput = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-300 outline-none focus:border-orange-500 transition-colors';
const textInput = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-300 outline-none focus:border-orange-500 transition-colors';
const submitBtn = 'w-full bg-orange-600 hover:bg-orange-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-semibold py-2 rounded transition-colors mt-4';
const fieldGroup = 'mb-4';

export function OnboardingModal() {
  const { t } = useTranslation();
  const { user, loadUser } = useAuth();
  const { showToast } = useToast();
  const [server, setServer] = useState('');
  const [gameId, setGameId] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const needsOnboarding = user && (!user.server || !user.game_id);

  const handleSubmit = useCallback(async () => {
    if (!server || !gameId.trim()) return;
    setSubmitting(true);
    try {
      await updateProfile({ server, game_id: gameId.trim() });
      await loadUser();
      showToast({ type: 'success', message: t('onboarding.complete') });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = detail === 'game_id_taken' ? t('onboarding.gameIdTaken') : t('onboarding.error');
      showToast({ type: 'error', message: msg });
    } finally {
      setSubmitting(false);
    }
  }, [server, gameId, loadUser, showToast, t]);

  const handleServerChange = useCallback((e) => setServer(e.target.value), []);
  const handleGameIdChange = useCallback((e) => setGameId(e.target.value), []);

  if (!needsOnboarding) return null;

  return (
    <div className={overlay}>
      <div className={card}>
        <h2 className={title}>
          {t('onboarding.welcome', { name: user.discord_username })}
        </h2>
        <p className={subtitle}>{t('onboarding.subtitle')}</p>

        <div className={fieldGroup}>
          <label className={label}>{t('onboarding.server')}</label>
          <select className={selectInput} value={server} onChange={handleServerChange}>
            <option value="">{t('onboarding.selectServer')}</option>
            {SERVERS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <div className={fieldGroup}>
          <label className={label}>{t('onboarding.gameId')}</label>
          <input
            type="text"
            className={textInput}
            value={gameId}
            onChange={handleGameIdChange}
            placeholder={t('onboarding.gameIdPlaceholder')}
            maxLength={20}
          />
        </div>

        <button
          type="button"
          className={submitBtn}
          disabled={!server || !gameId.trim() || submitting}
          onClick={handleSubmit}
        >
          {submitting ? t('onboarding.saving') : t('onboarding.submit')}
        </button>
      </div>
    </div>
  );
}
