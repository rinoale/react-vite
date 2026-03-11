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

export const searchListings = (q, tags, { limit, offset, gameItemId } = {}) =>
  client.get('/listings/search', { params: { q, tags, limit, offset, ...(gameItemId ? { game_item_id: gameItemId } : {}) } });

export const searchTags = (q) =>
  client.get('/tags/search', { params: { q } });

export const getHornBugleHistory = (serverName = '류트') =>
  client.get('/horn-bugle', { params: { server_name: serverName } });
