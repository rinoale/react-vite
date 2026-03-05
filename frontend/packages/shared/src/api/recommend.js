import client from './client';

export const getListings = (params) => client.get('/listings', { params });

export const getListingDetail = (listingId) => client.get(`/listings/${listingId}`);

export const getListingsByGameItem = (gameItemId) =>
  client.get('/listings', { params: { game_item_id: gameItemId } });

export const searchGameItems = (q) =>
  client.get('/game-items', { params: { q } });

export const searchListings = (q) =>
  client.get('/listings/search', { params: { q } });
