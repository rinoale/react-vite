import client from './client';

export const uploadItemV3 = (file) => {
  const form = new FormData();
  form.append('file', file);
  return client.post('/upload-item-v3', form);
};

export const registerListing = (payload) =>
  client.post('/register-listing', payload);
