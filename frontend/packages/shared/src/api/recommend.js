import client from './client';

export const getItems = () => client.get('/items');

export const getItemDetail = (itemId) => client.get(`/items/${itemId}`);
