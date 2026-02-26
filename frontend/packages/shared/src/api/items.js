import client from './client';

export const examineItem = (file) => {
  const form = new FormData();
  form.append('file', file);
  return client.post('/examine-item', form);
};

export const registerListing = (payload) =>
  client.post('/register-listing', payload);
