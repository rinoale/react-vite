import client from './client';

export const getListings = ({ limit, offset, ...rest } = {}) =>
  client.get('/listings', { params: { limit, offset, ...rest } });

export const getListingDetail = (listingId) => client.get(`/listings/${listingId}`);

export const getListingByCode = (code) => client.get(`/listings/s/${code}`);

export const getMyListings = ({ limit, offset } = {}) =>
  client.get('/listings/mine', { params: { limit, offset } });

export const updateListingStatus = (listingId, status) =>
  client.patch(`/listings/${listingId}/status`, { status });

export const getListingsByGameItem = (gameItemId) =>
  client.get('/listings', { params: { game_item_id: gameItemId } });

export const searchGameItems = (q) =>
  client.get('/game-items', { params: { q } });

const _OP_PREFIX = { gte: 'min_', lte: 'max_', eq: 'eq_' };

export const searchListings = (q, tags, { limit, offset, gameItemId, attrFilters } = {}) => {
  const attrParams = {};
  if (attrFilters) {
    for (const f of attrFilters) {
      if (f.key && f.value != null && f.value !== '') {
        const prefix = _OP_PREFIX[f.op] || 'min_';
        attrParams[`${prefix}${f.key}`] = parseInt(f.value, 10);
      }
    }
  }
  return client.get('/listings/search', {
    params: { q, tags, limit, offset, ...(gameItemId ? { game_item_id: gameItemId } : {}), ...attrParams },
  });
};

export const searchTags = (q) =>
  client.get('/tags/search', { params: { q } });

export const getHornBugleHistory = (serverName = '류트') =>
  client.get('/horn-bugle', { params: { server_name: serverName } });
