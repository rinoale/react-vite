import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.MABINOGI_TRADE_API_URL || 'http://localhost:8000',
});

export default client;
