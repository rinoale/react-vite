import client from './client';

export const examineItem = (file) => {
  const form = new FormData();
  form.append('file', file);
  return client.post('/examine-item', form);
};

/**
 * Start an async examine-item job and stream progress via SSE.
 *
 * @param {File} file - Image file to examine
 * @param {object} callbacks
 * @param {(step: string) => void} callbacks.onProgress - Called on each pipeline step
 * @param {(data: object) => void} callbacks.onResult - Called with the final result
 * @param {(error: Error) => void} callbacks.onError - Called on failure
 * @returns {{ close: () => void }} Handle to abort the stream
 */
export const examineItemStream = async (file, { onProgress, onResult, onError }) => {
  let evtSource = null;

  try {
    const form = new FormData();
    form.append('file', file);
    const { data } = await client.post('/examine-item', form);
    const jobId = data.job_id;

    const baseUrl = client.defaults.baseURL || '/api';
    evtSource = new EventSource(`${baseUrl}/examine-item/${jobId}/stream`);

    evtSource.addEventListener('progress', (e) => {
      onProgress?.(JSON.parse(e.data));
    });

    evtSource.addEventListener('result', (e) => {
      evtSource.close();
      onResult?.(JSON.parse(e.data));
    });

    evtSource.addEventListener('error', (e) => {
      evtSource.close();
      const msg = e.data ? JSON.parse(e.data).message : 'Connection lost';
      onError?.(new Error(msg));
    });
  } catch (err) {
    evtSource?.close();
    onError?.(err);
  }

  return {
    close: () => evtSource?.close(),
  };
};

export const registerListing = (payload) =>
  client.post('/register-listing', payload);
