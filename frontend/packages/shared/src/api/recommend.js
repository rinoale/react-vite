import client from './client';

export const getItems = () => client.get('/items');

export const getRecommendationsByItem = (itemId) =>
  client.get(`/recommend/item/${itemId}`);
