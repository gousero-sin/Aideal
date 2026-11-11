import test from 'node:test';
import assert from 'node:assert/strict';
import { createPanelDataCache, isAbortError } from '../services/panelDataCache.js';

const jsonResponse = (payload, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => payload,
});

function deferredFetch() {
  const calls = [];
  const fetchImpl = (url, init) => new Promise((resolve, reject) => {
    const call = { url, init, resolve, reject };
    init?.signal?.addEventListener('abort', () => {
      const error = new Error('aborted');
      error.name = 'AbortError';
      reject(error);
    });
    calls.push(call);
  });
  return { calls, fetchImpl };
}

test('requisições iguais em voo são compartilhadas e o resultado vai para o cache', async () => {
  const { calls, fetchImpl } = deferredFetch();
  const cache = createPanelDataCache({ fetchImpl });
  const first = cache.load('/api/dre/painel?ano=2025');
  const second = cache.load('/api/dre/painel?ano=2025');
  assert.equal(calls.length, 1);
  calls[0].resolve(jsonResponse({ kpis: { total: 1 } }));
  assert.deepEqual(await first, { kpis: { total: 1 } });
  assert.equal(await second, await first);
  assert.equal(cache.peek('/api/dre/painel?ano=2025').fresh, true);
  await cache.load('/api/dre/painel?ano=2025');
  assert.equal(calls.length, 1, 'entrada fresca não refaz a requisição');
});

test('abortar um consumidor só cancela a requisição quando ninguém mais espera', async () => {
  const { calls, fetchImpl } = deferredFetch();
  const cache = createPanelDataCache({ fetchImpl });
  const a = new AbortController();
  const b = new AbortController();
  const first = cache.load('/api/x', { signal: a.signal });
  const second = cache.load('/api/x', { signal: b.signal });
  a.abort();
  await assert.rejects(first, (error) => isAbortError(error));
  assert.equal(calls[0].init.signal.aborted, false);
  b.abort();
  await assert.rejects(second, (error) => isAbortError(error));
  assert.equal(calls[0].init.signal.aborted, true);
  assert.equal(cache.peek('/api/x'), null);
});

test('entrada expira pelo TTL e invalidação por prefixo marca como velha e avisa assinantes', async () => {
  let clock = 0;
  const fetchImpl = async (url) => jsonResponse({ url, clock });
  const cache = createPanelDataCache({ fetchImpl, now: () => clock, ttlMs: 1000 });
  await cache.load('/api/dre/painel?ano=2025');
  await cache.load('/api/fluxo_caixa/painel?ano=2025');
  clock = 999;
  assert.equal(cache.peek('/api/dre/painel?ano=2025').fresh, true);
  clock = 1000;
  assert.equal(cache.peek('/api/dre/painel?ano=2025').fresh, false);

  clock = 0;
  await cache.load('/api/dre/painel?ano=2025', { force: true });
  const notified = [];
  const unsubscribe = cache.subscribe((prefix) => notified.push(prefix));
  cache.invalidate('/api/dre/');
  unsubscribe();
  cache.invalidate('/api/fluxo_caixa/');
  assert.deepEqual(notified, ['/api/dre/']);
  assert.equal(cache.peek('/api/dre/painel?ano=2025').fresh, false);
  assert.ok(cache.peek('/api/dre/painel?ano=2025').data, 'dados velhos continuam disponíveis');
});

test('erro HTTP usa o detail da API e não grava cache', async () => {
  const cache = createPanelDataCache({
    fetchImpl: async () => jsonResponse({ detail: 'Ano inválido' }, 422),
  });
  await assert.rejects(cache.load('/api/dre/painel?ano=1'), /Ano inválido/);
  assert.equal(cache.peek('/api/dre/painel?ano=1'), null);
});

test('prime registra a resposta canônica sem sobrescrever entrada fresca; clear limpa tudo', async () => {
  const cache = createPanelDataCache({ fetchImpl: async () => jsonResponse({ origem: 'rede' }) });
  cache.prime('/api/dre/painel?ano=2025', { origem: 'prime' });
  cache.prime('/api/dre/painel?ano=2025', { origem: 'segundo' });
  assert.deepEqual(await cache.load('/api/dre/painel?ano=2025'), { origem: 'prime' });
  cache.clear();
  assert.equal(cache.peek('/api/dre/painel?ano=2025'), null);
});

test('limita o número de entradas descartando as mais antigas', async () => {
  const cache = createPanelDataCache({ fetchImpl: async (url) => jsonResponse({ url }), maxEntries: 2 });
  await cache.load('/a');
  await cache.load('/b');
  await cache.load('/c');
  assert.equal(cache.peek('/a'), null);
  assert.ok(cache.peek('/b'));
  assert.ok(cache.peek('/c'));
});
