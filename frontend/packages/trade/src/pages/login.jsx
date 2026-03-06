import { useEffect, useRef, useCallback } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@mabi/shared/hooks/useAuth';
import { useToast } from '@mabi/shared/components/useToast';
import client from '@mabi/shared/api/client';
import { getDiscordAuthUrl } from '@mabi/shared/api/auth';

const authFormWrapper = 'min-h-screen flex items-center justify-center bg-gray-900';
const authCard = 'w-full max-w-sm bg-gray-800 rounded-lg border border-gray-700 p-6';
const authTitle = 'text-xl font-bold text-white text-center mb-6';
const discordBtn = 'w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2 rounded transition-colors flex items-center justify-center gap-2';

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { loginWithTokens } = useAuth();
  const { showToast } = useToast();
  const callbackHandled = useRef(false);

  useEffect(() => {
    if (callbackHandled.current) return;
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    const error = searchParams.get('error');

    if (error) {
      callbackHandled.current = true;
      showToast({ type: 'error', message: t(`auth.discordError.${error}`, t('auth.error')) });
      return;
    }
    if (accessToken && refreshToken) {
      callbackHandled.current = true;
      loginWithTokens(accessToken, refreshToken).then(() => {
        showToast({ type: 'success', message: t('auth.loginSuccess') });
        navigate(location.state?.from || '/', { replace: true });
      });
    }
  }, [searchParams, loginWithTokens, navigate, location.state, showToast, t]);

  const handleDiscord = useCallback(() => {
    window.location.href = `${client.defaults.baseURL}${getDiscordAuthUrl()}`;
  }, []);

  return (
    <div className={authFormWrapper}>
      <div className={authCard}>
        <h1 className={authTitle}>{t('auth.loginTitle')}</h1>
        <button type="button" className={discordBtn} onClick={handleDiscord}>
          Discord
        </button>
      </div>
    </div>
  );
}
