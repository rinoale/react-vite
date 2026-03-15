import client from './client';

export const getSummary = () => client.get('/admin/summary');

export const getEnchantEntries = ({ q, id, limit, offset } = {}) =>
  client.get('/admin/enchants', { params: { q: q || '', id: id || '', limit, offset } });

export const getEnchantEffects = (enchantId) =>
  client.get(`/admin/enchants/${enchantId}/effects`);

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

export const getListings = ({ q, id, limit, offset } = {}) =>
  client.get('/admin/listings', { params: { q: q || '', id: id || '', limit, offset } });

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

export const getUniqueTags = ({ q, sort, limit, offset } = {}) =>
  client.get('/admin/tags/unique', { params: { q: q || '', sort: sort || '', limit, offset } });

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

export const getEchostoneOptions = ({ q, id, limit, offset } = {}) =>
  client.get('/admin/echostone-options', { params: { q: q || '', id: id || '', limit, offset } });

export const getMuriasRelicOptions = ({ q, id, limit, offset } = {}) =>
  client.get('/admin/murias-relic-options', { params: { q: q || '', id: id || '', limit, offset } });

export const getReforgeOptions = ({ q, id, limit, offset } = {}) =>
  client.get('/admin/reforge-options', { params: { q: q || '', id: id || '', limit, offset } });

export const getEffects = ({ limit, offset } = {}) =>
  client.get('/admin/effects', { params: { limit, offset } });

export const getGameItems = ({ q, id, limit, offset } = {}) =>
  client.get('/admin/game-items', { params: { q: q || '', id: id || '', limit, offset } });

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

export const createFeatureFlag = (name) =>
  client.post('/admin/feature-flags', { name });

export const deleteFeatureFlag = (flagId) =>
  client.delete(`/admin/feature-flags/${flagId}`);

export const assignRole = (userId, roleName) =>
  client.post(`/admin/users/${userId}/roles/${roleName}`);

export const removeRole = (userId, roleName) =>
  client.delete(`/admin/users/${userId}/roles/${roleName}`);

export const assignFeatureToRole = (roleName, flagName) =>
  client.post(`/admin/roles/${roleName}/features/${flagName}`);

export const removeFeatureFromRole = (roleName, flagName) =>
  client.delete(`/admin/roles/${roleName}/features/${flagName}`);

export const getR2Usage = () =>
  client.get('/admin/usage/r2');

export const getOciUsage = () =>
  client.get('/admin/usage/oci');

export const getActivityLogs = ({ action, userId, limit, offset } = {}) =>
  client.get('/admin/activity-logs', { params: { action: action || '', ...(userId ? { user_id: userId } : {}), limit, offset } });

export const getActivityActions = () =>
  client.get('/admin/activity-logs/actions');

export const getSystemLogs = ({ source, action, limit, offset } = {}) =>
  client.get('/admin/system-logs', { params: { source: source || '', action: action || '', limit, offset } });

export const getSystemLogActions = () =>
  client.get('/admin/system-logs/actions');

export const getAutoTagRules = ({ limit, offset } = {}) =>
  client.get('/admin/auto-tag-rules', { params: { limit, offset } });

export const createAutoTagRule = (data) =>
  client.post('/admin/auto-tag-rules', data);

export const updateAutoTagRule = (ruleId, data) =>
  client.patch(`/admin/auto-tag-rules/${ruleId}`, data);

export const deleteAutoTagRule = (ruleId) =>
  client.delete(`/admin/auto-tag-rules/${ruleId}`);
