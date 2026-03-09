import client from './client';

export const getListings = ({ limit, offset, ...rest } = {}) =>
  client.get('/listings', { params: { limit, offset, ...rest } });

export const getListingDetail = (listingId) => client.get(`/listings/${listingId}`);

export const getListingsByGameItem = (gameItemId) =>
  client.get('/listings', { params: { game_item_id: gameItemId } });

export const searchGameItems = (q) =>
  client.get('/game-items', { params: { q } });

export const searchListings = (q, tags, { limit, offset } = {}) =>
  client.get('/listings/search', { params: { q, tags, limit, offset } });

export const searchTags = (q) =>
  client.get('/tags/search', { params: { q } });

export const getHornBugleHistory = (serverName = '류트') =>
  client.get('/horn-bugle', { params: { server_name: serverName } });
