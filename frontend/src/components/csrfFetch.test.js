import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchWithCsrfRecovery } from '../auth/csrfFetch.js';

const json = (body, status = 200) => new Response(JSON.stringify(body), { status });

test('recupera token da sessão e repete somente escrita rejeitada por CSRF', async () => {
  const calls = [];
  const responses = [json({ detail: 'Token CSRF inválido.' }, 403),
    json({ authenticated: true, csrf_token: 'fresh' }), json({ saved: true })];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return responses.shift();
  };
  const options = { method: 'PATCH', body: '{"dfp":{}}', headers: { 'Content-Type': 'application/json' } };
  const response = await fetchWithCsrfRecovery('/api/orcamento/revisoes/1', options,
    { csrfToken: 'old', apiBase: '/api', fetchImpl });
  assert.deepEqual(await response.json(), { saved: true });
  assert.equal(calls.length, 3);
  assert.equal(calls[1].url, '/api/auth/session');
  assert.equal(calls[2].options.headers.get('X-CSRF-Token'), 'fresh');
  assert.equal(calls[2].options.body, options.body);
  assert.equal(calls[2].options.credentials, 'same-origin');
  assert.deepEqual(options.headers, { 'Content-Type': 'application/json' });
});

for (const [status, detail] of [[403, 'Permissão insuficiente.'], [401, 'Sessão obrigatória.'], [500, 'Falha']]) {
  test(`não repete erro ${status} alheio ao CSRF`, async () => {
    let calls = 0;
    const response = await fetchWithCsrfRecovery('/api/test', { method: 'POST' }, {
      fetchImpl: async () => { calls += 1; return json({ detail }, status); },
    });
    assert.equal(calls, 1);
    assert.equal((await response.json()).detail, detail);
  });
}

test('limita a uma repetição mesmo quando token renovado falha', async () => {
  let calls = 0;
  const response = await fetchWithCsrfRecovery('/api/test', { method: 'POST' }, {
    fetchImpl: async (url) => {
      calls += 1;
      return url.endsWith('/session') ? json({ authenticated: true, csrf_token: 'new' })
        : json({ detail: 'Token CSRF inválido.' }, 403);
    },
  });
  assert.equal(calls, 3);
  assert.equal(response.status, 403);
});

test('sessão expirada preserva rejeição original sem repetir escrita', async () => {
  let calls = 0;
  const response = await fetchWithCsrfRecovery('/api/test', { method: 'PATCH' }, {
    fetchImpl: async (url) => {
      calls += 1;
      return url.endsWith('/session') ? json({ authenticated: false }, 401)
        : json({ detail: 'Token CSRF inválido.' }, 403);
    },
  });
  assert.equal(calls, 2);
  assert.equal(response.status, 403);
});

test('GET não envia token nem tenta recuperar CSRF', async () => {
  let calls = 0;
  await fetchWithCsrfRecovery('/api/test', {}, {
    csrfToken: 'secret', fetchImpl: async (_url, options) => {
      calls += 1;
      assert.equal(options.headers.has('X-CSRF-Token'), false);
      return json({ detail: 'Token CSRF inválido.' }, 403);
    },
  });
  assert.equal(calls, 1);
});
