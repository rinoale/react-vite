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

export const truncateCorrections = () =>
  client.delete('/admin/corrections/truncate');

export const getListings = ({ limit, offset }) =>
  client.get('/admin/listings', { params: { limit, offset } });

export const getListingDetail = (listingId) =>
  client.get(`/admin/listings/${listingId}/detail`);

export const getTags = ({ targetType, limit, offset }) =>
  client.get('/admin/tags', { params: { target_type: targetType || '', limit, offset } });

export const createTag = ({ target_type, target_id, name, weight }) =>
  client.post('/admin/tags', { target_type, target_id, name, weight });

export const deleteTag = (tagId) =>
  client.delete(`/admin/tags/${tagId}`);

export const searchTagEntities = (targetType, q) =>
  client.get('/admin/tags/search-entities', { params: { target_type: targetType, q } });
