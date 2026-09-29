import test from 'node:test';
import assert from 'node:assert/strict';

import {
  createAuthClient,
  normalizeSession,
  readApiError,
} from '../auth/authClient.js';

test('normaliza sessao autenticada e remove permissoes duplicadas ou invalidas', () => {
  assert.deepEqual(normalizeSession({
    authenticated: true,
    user: { id: 'u-1', username: 'eduardo', display_name: 'Eduardo' },
    permissions: ['users.manage', '', 'users.manage', null],
    modules: ['usuarios'],
    csrf_token: 'csrf',
    password_change_required: true,
  }), {
    authenticated: true,
    user: { id: 'u-1', username: 'eduardo', displayName: 'Eduardo' },
    permissions: ['users.manage'],
    modules: ['usuarios'],
    csrfToken: 'csrf',
    passwordChangeRequired: true,
  });
});

test('sessao malformada permanece anonima e negada por padrao', () => {
  assert.deepEqual(normalizeSession({ authenticated: true }), {
    authenticated: false,
    user: null,
    permissions: [],
    modules: [],
    csrfToken: null,
    passwordChangeRequired: false,
  });
});

test('cliente envia cookie, JSON e token CSRF nas operacoes', async () => {
  const calls = [];
  const fakeFetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      json: async () => ({ authenticated: false }),
    };
  };
  const client = createAuthClient({ apiBase: '/api', fetchImpl: fakeFetch });

  await client.login({ username: 'eduardo', password: 'segredo' });
  await client.logout('csrf-123');
  await client.changePassword({
    currentPassword: 'senha-temporaria',
    newPassword: 'senha-definitiva-segura',
  }, 'csrf-456');

  assert.equal(calls[0].url, '/api/auth/login');
  assert.equal(calls[0].options.credentials, 'same-origin');
  assert.equal(calls[0].options.headers['Content-Type'], 'application/json');
  assert.equal(calls[1].options.headers['X-CSRF-Token'], 'csrf-123');
  assert.equal(calls[2].url, '/api/auth/change-password');
  assert.equal(calls[2].options.method, 'POST');
  assert.equal(calls[2].options.headers['X-CSRF-Token'], 'csrf-456');
  assert.deepEqual(JSON.parse(calls[2].options.body), {
    current_password: 'senha-temporaria',
    new_password: 'senha-definitiva-segura',
  });
});

test('extrai erro seguro de detail, error ou status HTTP', async () => {
  assert.equal(await readApiError({
    status: 403,
    json: async () => ({ detail: 'Acesso negado.' }),
  }), 'Acesso negado.');
  assert.equal(await readApiError({
    status: 500,
    json: async () => { throw new Error('invalid json'); },
  }), 'Nao foi possivel concluir a solicitacao (HTTP 500).');
});

test('cliente cobre consulta de sessao e ciclo de gestao de usuarios', async () => {
  const calls = [];
  const temporaryPassword = 'senha-de-teste-123';
  const fakeFetch = async (url, options) => {
    calls.push({ url, options });
    if (url.endsWith('/auth/session')) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          authenticated: true,
          user: { id: 'u-1', username: 'eduardo' },
          permissions: [],
          modules: [],
        }),
      };
    }
    return { ok: true, status: 200, json: async () => ({ users: [] }) };
  };
  const client = createAuthClient({ apiBase: '/api/', fetchImpl: fakeFetch });

  const session = await client.getSession();
  await client.listUsers();
  await client.createUser({ username: 'maria' }, 'csrf');
  await client.updateUser('id/seguro', { active: false }, 'csrf');
  await client.updateUser('id/seguro', { password: temporaryPassword }, 'csrf');
  await client.deleteUser('id/seguro', 'csrf');

  assert.equal(session.user.displayName, 'eduardo');
  assert.deepEqual(calls.map(({ url }) => url), [
    '/api/auth/session',
    '/api/admin/users',
    '/api/admin/users',
    '/api/admin/users/id%2Fseguro',
    '/api/admin/users/id%2Fseguro',
    '/api/admin/users/id%2Fseguro',
  ]);
  assert.equal(calls[3].options.method, 'PATCH');
  assert.deepEqual(JSON.parse(calls[4].options.body), { password: temporaryPassword });
  assert.equal(calls[5].options.method, 'DELETE');
  assert.equal(calls[5].options.headers['X-CSRF-Token'], 'csrf');
  assert.equal(calls[5].options.body, undefined);
});

test('cliente aceita logout sem corpo e propaga erro HTTP seguro', async () => {
  const successClient = createAuthClient({
    fetchImpl: async () => ({ ok: true, status: 204 }),
  });
  assert.equal(await successClient.logout(), null);

  const failingClient = createAuthClient({
    fetchImpl: async () => ({
      ok: false,
      status: 401,
      json: async () => ({ error: 'Sessao expirada.' }),
    }),
  });
  await assert.rejects(() => failingClient.listUsers(), /Sessao expirada/);
});

test('cliente rejeita implementacao de fetch ausente', () => {
  assert.throws(() => createAuthClient({ fetchImpl: null }), /fetch/);
});
