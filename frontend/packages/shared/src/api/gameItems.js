import client from './client';

export const searchGameItems = (q) =>
  client.get('/game-items', { params: { q } });
