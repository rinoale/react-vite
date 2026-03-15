import client from './client';

export const getHornBugleHistory = (serverName = '류트') =>
  client.get('/misc/horn-bugle', { params: { server_name: serverName } });
