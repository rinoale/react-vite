import { useState, useCallback, useEffect } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@mabi/shared/hooks/useAuth';
import { useToast } from '@mabi/shared/components/useToast';
import { inputDefault } from '@mabi/shared/styles';
import client from '@mabi/shared/api/client';
import { getDiscordAuthUrl } from '@mabi/shared/api/auth';

const authFormWrapper = 'min-h-screen flex items-center justify-center bg-gray-900';
const authCard = 'w-full max-w-sm bg-gray-800 rounded-lg border border-gray-700 p-6';
const authTitle = 'text-xl font-bold text-white text-center mb-6';
const authLabel = 'block text-sm text-gray-400 mb-1';
const authFieldGroup = 'mb-4';
const authSubmitBtn = 'w-full bg-orange-600 hover:bg-orange-500 text-white font-semibold py-2 rounded transition-colors';
const authToggleText = 'text-center text-sm text-gray-400 mt-4';
const authToggleLink = 'text-orange-400 hover:text-orange-300 cursor-pointer ml-1';
const authDivider = 'flex items-center gap-3 my-4 text-gray-500 text-sm';
const authDividerLine = 'flex-1 border-t border-gray-700';
const discordBtn = 'w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 rounded transition-colors flex items-center justify-center gap-2';

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { login, loginWithTokens, register } = useAuth();
  const { showToast } = useToast();

  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    const error = searchParams.get('error');

    if (error) {
      showToast({ type: 'error', message: t(`auth.discordError.${error}`, t('auth.error')) });
      return;
    }
    if (accessToken && refreshToken) {
      loginWithTokens(accessToken, refreshToken).then(() => {
        showToast({ type: 'success', message: t('auth.loginSuccess') });
        navigate(location.state?.from || '/', { replace: true });
      });
    }
  }, [searchParams, loginWithTokens, navigate, location.state, showToast, t]);

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(email, password);
        showToast({ type: 'success', message: t('auth.registerSuccess') });
      } else {
        await login(email, password);
        showToast({ type: 'success', message: t('auth.loginSuccess') });
      }
      navigate(location.state?.from || '/');
    } catch (err) {
      const detail = err.response?.data?.detail || t('auth.error');
      showToast({ type: 'error', message: detail });
    } finally {
      setSubmitting(false);
    }
  }, [isRegister, email, password, login, register, navigate, location.state, showToast, t]);

  const handleEmailChange = useCallback((e) => setEmail(e.target.value), []);
  const handlePasswordChange = useCallback((e) => setPassword(e.target.value), []);
  const handleToggle = useCallback(() => setIsRegister((v) => !v), []);

  const handleDiscord = useCallback(() => {
    window.location.href = `${client.defaults.baseURL}${getDiscordAuthUrl()}`;
  }, []);

  return (
    <div className={authFormWrapper}>
      <div className={authCard}>
        <h1 className={authTitle}>
          {isRegister ? t('auth.registerTitle') : t('auth.loginTitle')}
        </h1>
        <form onSubmit={handleSubmit}>
          <div className={authFieldGroup}>
            <label className={authLabel}>{t('auth.email')}</label>
            <input
              type="email"
              className={inputDefault}
              value={email}
              onChange={handleEmailChange}
              required
              autoComplete="email"
            />
          </div>
          <div className={authFieldGroup}>
            <label className={authLabel}>{t('auth.password')}</label>
            <input
              type="password"
              className={inputDefault}
              value={password}
              onChange={handlePasswordChange}
              required
              minLength={8}
              autoComplete={isRegister ? 'new-password' : 'current-password'}
            />
          </div>
          <button type="submit" className={authSubmitBtn} disabled={submitting}>
            {isRegister ? t('auth.registerSubmit') : t('auth.loginSubmit')}
          </button>
        </form>

        <div className={authDivider}>
          <span className={authDividerLine} />
          <span>{t('auth.or')}</span>
          <span className={authDividerLine} />
        </div>

        <button type="button" className={discordBtn} onClick={handleDiscord}>
          Discord
        </button>

        <p className={authToggleText}>
          {isRegister ? t('auth.hasAccount') : t('auth.noAccount')}
          <span className={authToggleLink} onClick={handleToggle} role="button" tabIndex={0} onKeyDown={handleToggle}>
            {isRegister ? t('auth.loginSubmit') : t('auth.registerSubmit')}
          </span>
        </p>
      </div>
    </div>
  );
}
