import client from './client';

export const getSummary = () => client.get('/admin/summary');

export const getEnchantEntries = ({ limit, offset }) =>
  client.get('/admin/enchant-entries', { params: { limit, offset } });

export const getEnchantEffects = (enchantId) =>
  client.get(`/admin/enchant-entries/${enchantId}/effects`);

export const getLinks = ({ limit, offset }) =>
  client.get('/admin/links', { params: { limit, offset } });

export const getCorrections = ({ status, limit, offset }) =>
  client.get('/admin/corrections/list', { params: { status, limit, offset } });

export const approveCorrection = (correctionId) =>
  client.post(`/admin/corrections/approve/${correctionId}`);

export const editCorrection = (correctionId, correctedText) =>
  client.patch(`/admin/corrections/${correctionId}`, { corrected_text: correctedText });

export const getItems = ({ limit, offset }) =>
  client.get('/admin/items', { params: { limit, offset } });
