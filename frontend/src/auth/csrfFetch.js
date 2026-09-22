const isCsrfRejection = async (response) => {
  if (response.status !== 403) return false;
  try {
    const payload = await response.clone().json();
    return payload?.detail === 'Token CSRF inválido.';
  } catch {
    return false;
  }
};

// Retry only a server-confirmed CSRF rejection, which occurs before any mutation.
// Network errors and permission failures must never replay a write.
export async function fetchWithCsrfRecovery(
  url,
  options = {},
  { csrfToken, apiBase = '/api', fetchImpl = globalThis.fetch } = {},
) {
  const method = (options.method || 'GET').toUpperCase();
  const writes = !['GET', 'HEAD', 'OPTIONS'].includes(method);
  const headers = new Headers(options.headers);
  if (writes && csrfToken) headers.set('X-CSRF-Token', csrfToken);
  const requestOptions = { credentials: 'same-origin', ...options, method, headers };
  const response = await fetchImpl(url, requestOptions);
  if (!writes || !await isCsrfRejection(response)) return response;

  const sessionResponse = await fetchImpl(
    `${String(apiBase).replace(/\/$/, '')}/auth/session`,
    { method: 'GET', credentials: requestOptions.credentials, cache: 'no-store', signal: options.signal },
  );
  if (!sessionResponse.ok) return response;
  const session = await sessionResponse.json();
  if (!session?.authenticated || !session.csrf_token) return response;
  const retryHeaders = new Headers(headers);
  retryHeaders.set('X-CSRF-Token', session.csrf_token);
  return fetchImpl(url, { ...requestOptions, headers: retryHeaders });
}
