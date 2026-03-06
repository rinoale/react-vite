import client from './client';

export function getMe() {
  return client.get('/auth/me');
}

export function logout() {
  return client.post('/auth/logout');
}

export function updateProfile(data) {
  return client.patch('/auth/me', data);
}

export function getDiscordAuthUrl() {
  return '/auth/discord';
}
