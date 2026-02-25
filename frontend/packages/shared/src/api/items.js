import client from './client';

export const uploadItemV3 = (file) => {
  const form = new FormData();
  form.append('file', file);
  return client.post('/upload-item-v3', form);
};

export const registerItem = (payload) =>
  client.post('/register-item', payload);
