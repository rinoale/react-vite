import client from './client';

export function register(email, password) {
  return client.post('/auth/register', { email, password });
}

export function login(email, password) {
  return client.post('/auth/login', { email, password });
}

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
