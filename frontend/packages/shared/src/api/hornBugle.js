import client from './client';

export const getHornBugleHistory = (serverName = '류트') =>
  client.get('/horn-bugle', { params: { server_name: serverName } });
