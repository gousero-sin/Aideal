const ANONYMOUS_SESSION = Object.freeze({
  authenticated: false,
  user: null,
  permissions: [],
  modules: [],
  csrfToken: null,
  passwordChangeRequired: false,
});

const uniqueStrings = (values) => [
  ...new Set((Array.isArray(values) ? values : []).filter((value) => (
    typeof value === 'string' && value.trim()
  ))),
];

export const normalizeSession = (payload) => {
  const user = payload?.user;
  if (!payload?.authenticated || !user?.id || !user?.username) {
    return { ...ANONYMOUS_SESSION };
  }

  return {
    authenticated: true,
    user: {
      id: String(user.id),
      username: String(user.username),
      displayName: String(user.display_name || user.displayName || user.username),
    },
    permissions: uniqueStrings(payload.permissions),
    modules: Array.isArray(payload.modules) ? [...payload.modules] : [],
    csrfToken: payload.csrf_token || payload.csrfToken || null,
    passwordChangeRequired: Boolean(
      payload.password_change_required ?? payload.passwordChangeRequired ?? false,
    ),
  };
};

export const readApiError = async (response) => {
  try {
    const payload = await response.json();
    const message = payload?.detail || payload?.error || payload?.message;
    if (typeof message === 'string' && message.trim()) return message;
  } catch {
    // A resposta pode ser vazia ou não-JSON; o fallback não expõe conteúdo interno.
  }
  return `Nao foi possivel concluir a solicitacao (HTTP ${response.status}).`;
};

const joinApiPath = (apiBase, path) => `${String(apiBase || '/api').replace(/\/$/, '')}${path}`;

export const createAuthClient = ({ apiBase = '/api', fetchImpl = globalThis.fetch } = {}) => {
  if (typeof fetchImpl !== 'function') {
    throw new TypeError('Uma implementacao de fetch e obrigatoria.');
  }

  const request = async (
    path,
    { method = 'GET', body, csrfToken, anonymousOnUnauthorized = false } = {},
  ) => {
    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken;

    const response = await fetchImpl(joinApiPath(apiBase, path), {
      method,
      credentials: 'same-origin',
      headers,
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });

    if (response.status === 401 && anonymousOnUnauthorized) return null;
    if (!response.ok) throw new Error(await readApiError(response));
    if (response.status === 204) return null;
    return response.json();
  };

  return Object.freeze({
    getSession: async () => normalizeSession(await request('/auth/session', {
      anonymousOnUnauthorized: true,
    })),
    login: async (credentials) => normalizeSession(await request('/auth/login', {
      method: 'POST',
      body: credentials,
    })),
    logout: async (csrfToken) => request('/auth/logout', {
      method: 'POST',
      csrfToken,
    }),
    changePassword: async ({ currentPassword, newPassword }, csrfToken) => (
      normalizeSession(await request('/auth/change-password', {
        method: 'POST',
        body: {
          current_password: currentPassword,
          new_password: newPassword,
        },
        csrfToken,
      }))
    ),
    listUsers: async () => request('/admin/users'),
    createUser: async (user, csrfToken) => request('/admin/users', {
      method: 'POST',
      body: user,
      csrfToken,
    }),
    updateUser: async (userId, patch, csrfToken) => request(
      `/admin/users/${encodeURIComponent(userId)}`,
      { method: 'PATCH', body: patch, csrfToken },
    ),
    deleteUser: async (userId, csrfToken) => request(
      `/admin/users/${encodeURIComponent(userId)}`,
      { method: 'DELETE', csrfToken },
    ),
  });
};

export { ANONYMOUS_SESSION };
