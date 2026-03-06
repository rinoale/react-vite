import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
  paramsSerializer: { indexes: null },
});

let isRefreshing = false;
let pendingQueue = [];

function processQueue(error) {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve();
  });
  pendingQueue = [];
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || original._retry || original.url?.includes('/auth/')) {
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then(() => client(original));
    }

    original._retry = true;
    isRefreshing = true;

    try {
      await axios.post(
        `${client.defaults.baseURL}/auth/refresh`,
        {},
        { withCredentials: true },
      );
      processQueue(null);
      return client(original);
    } catch (refreshError) {
      processQueue(refreshError);
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);

export default client;
