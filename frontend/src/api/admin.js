import client from './client';

export const getSummary = () => client.get('/admin/summary');

export const getEnchantEntries = ({ limit, offset }) =>
  client.get('/admin/enchant-entries', { params: { limit, offset } });

export const getEnchantEffects = (enchantId) =>
  client.get(`/admin/enchant-entries/${enchantId}/effects`);

export const getLinks = ({ limit, offset }) =>
  client.get('/admin/links', { params: { limit, offset } });
