import { CONSTANTS } from '@/constants';
import { ApiClient } from './client';

export const apiClient = new ApiClient({
  baseUrlHttp: CONSTANTS.BACKEND_HTTP_API_URL,
  baseUrlWs: CONSTANTS.BACKEND_WS_API_URL,
});
