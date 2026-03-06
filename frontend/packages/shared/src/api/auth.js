import client from './client';

export function refresh(refreshToken) {
  return client.post('/auth/refresh', { refresh_token: refreshToken });
}

export function getMe() {
  return client.get('/auth/me');
}

export function updateProfile(data) {
  return client.patch('/auth/me', data);
}

export function getDiscordAuthUrl() {
  return '/auth/discord';
}
