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

export const searchTagEntities = (targetType, q, { like = true } = {}) =>
  client.get('/admin/tags/search-entities', { params: { target_type: targetType, q, like } });

export const bulkCreateTags = ({ targets, names, weight }) =>
  client.post('/admin/tags/bulk', { targets, names, ...(weight != null && { weight }) });

export const getUniqueTags = ({ limit, offset }) =>
  client.get('/admin/tags/unique', { params: { limit, offset } });

export const deleteTagById = (tagId) =>
  client.delete(`/admin/tags/by-tag/${tagId}`);

export const getTagDetail = (tagId) =>
  client.get(`/admin/tags/${tagId}`);

export const updateTagWeight = (tagId, weight) =>
  client.patch(`/admin/tags/${tagId}`, { weight });

export const updateTagTargetWeight = (tagTargetId, weight) =>
  client.patch(`/admin/tags/targets/${tagTargetId}`, { weight });

export const bulkUpdateTagTargetWeights = (ids, weight) =>
  client.patch('/admin/tags/targets/bulk', { ids, weight });

export const getJobs = () =>
  client.get('/admin/jobs');

export const triggerJob = (jobName) =>
  client.post(`/admin/jobs/${jobName}/run`);

export const getJobHistory = ({ jobName, limit, offset } = {}) =>
  client.get('/admin/jobs/history', { params: { job_name: jobName || '', limit, offset } });

export const getUsers = ({ limit, offset } = {}) =>
  client.get('/admin/users', { params: { limit, offset } });

export const getRoles = () =>
  client.get('/admin/roles');

export const getFeatureFlags = () =>
  client.get('/admin/feature-flags');

export const assignRole = (userId, roleName) =>
  client.post(`/admin/users/${userId}/roles/${roleName}`);

export const removeRole = (userId, roleName) =>
  client.delete(`/admin/users/${userId}/roles/${roleName}`);

export const assignFeatureToRole = (roleName, flagName) =>
  client.post(`/admin/roles/${roleName}/features/${flagName}`);

export const removeFeatureFromRole = (roleName, flagName) =>
  client.delete(`/admin/roles/${roleName}/features/${flagName}`);
