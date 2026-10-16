export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

const messages = {
  400: 'Please check your email and password.',
  401: 'Your session is no longer valid. Please sign in again.',
  403: 'You do not have permission to perform this action.',
  409: 'An account with this email already exists.',
  413: 'The submitted information is too large.',
  429: 'Too many requests. Please try again later.',
  503: 'The authentication service is unavailable. Please try again later.',
};

export function createApiClient({ baseUrl = '/api', fetchImpl = globalThis.fetch } = {}) {
  const base = baseUrl.trim().replace(/\/+$/, '');
  if (!base || !(base.startsWith('/') && !base.startsWith('//') || /^https?:\/\//.test(base))) {
    throw new Error('VITE_API_BASE_URL must be an API path or an HTTP(S) URL.');
  }
  let token = null;
  let onUnauthorized = () => {};
  return {
    setToken(value) { token = value; },
    setUnauthorizedHandler(handler) { onUnauthorized = handler; },
    async request(path, { method = 'GET', body, authenticated = false, signal, responseType = 'json', downloadToken } = {}) {
      const requestToken = authenticated ? token : null;
      if (authenticated && !requestToken) throw new ApiError(messages[401], 401);
      let response;
      try {
        response = await fetchImpl(`${base}${path}`, {
          method, signal, credentials: 'omit', cache: 'no-store', redirect: 'error',
          headers: {
            Accept: responseType === 'blob' ? 'application/pdf' : 'application/json',
            ...(downloadToken ? { 'X-Report-Link': downloadToken } : {}),
            ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
            ...(requestToken ? { Authorization: `Bearer ${requestToken}` } : {}),
          },
          ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
        });
      } catch (error) {
        if (error.name === 'AbortError') throw error;
        throw new ApiError('Unable to connect to AYUR-SAGE. Please try again.');
      }
      if (response.ok && responseType === 'blob') {
        if (response.headers.get('content-type')?.split(';')[0] !== 'application/pdf') throw new ApiError('The report service returned an unexpected document.');
        return response.blob();
      }
      let data;
      try { data = await response.json(); } catch { /* A proxy may return HTML. */ }
      if (!response.ok) {
        // Flask errors are {error: {code, message}}; use safe, consistent UI copy.
        if (response.status === 401 && requestToken && requestToken === token) onUnauthorized();
        const message = response.status === 401 && !authenticated
          ? 'Email or password is incorrect.'
          : messages[response.status] || 'The request could not be completed. Please try again.';
        const error = new ApiError(message, response.status);
        // Resource services inspect structured errors; session handling is unchanged.
        error.response = data;
        throw error;
      }
      if (!data || typeof data !== 'object' || Array.isArray(data)) {
        throw new ApiError('The service returned an unexpected response. Please try again.');
      }
      return data;
    },
  };
}
