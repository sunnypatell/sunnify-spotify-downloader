import { ApiClient } from './client';

export const apiClient = new ApiClient({
  baseUrlHttp: 'http://127.0.0.1:8000',
  baseUrlWs: 'ws://127.0.0.1:8000',
});
