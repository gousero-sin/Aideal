// Cache em memória das respostas GET dos painéis (DRE, Fluxo de Caixa).
//
// - Uma entrada por URL completa (inclui a query de filtros).
// - Requisições idênticas em voo são compartilhadas (dedupe); a requisição
//   real só é abortada quando todos os consumidores desistem dela.
// - Invalidação por prefixo marca entradas como velhas e avisa os assinantes,
//   que revalidam em segundo plano mantendo os dados atuais na tela.
//
// O módulo não depende de React para poder ser testado com node --test.

export const DEFAULT_PANEL_TTL_MS = 60_000;
const MAX_ENTRIES = 40;

const createAbortError = () => {
  if (typeof DOMException === 'function') {
    return new DOMException('A requisição foi cancelada.', 'AbortError');
  }
  const error = new Error('A requisição foi cancelada.');
  error.name = 'AbortError';
  return error;
};

export const isAbortError = (error) => error?.name === 'AbortError';

const readErrorDetail = async (response, fallbackMessage) => {
  const payload = await response.json().catch(() => ({}));
  const detail = payload?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return fallbackMessage || `Não foi possível carregar os dados (HTTP ${response.status}).`;
};

export function createPanelDataCache({
  fetchImpl = (...args) => globalThis.fetch(...args),
  now = () => Date.now(),
  ttlMs = DEFAULT_PANEL_TTL_MS,
  maxEntries = MAX_ENTRIES,
} = {}) {
  const entries = new Map();
  const inflight = new Map();
  const listeners = new Set();

  const remember = (url, data) => {
    entries.delete(url);
    entries.set(url, { data, updatedAt: now(), stale: false });
    while (entries.size > maxEntries) {
      entries.delete(entries.keys().next().value);
    }
  };

  const peek = (url) => {
    const entry = entries.get(url);
    if (!entry) return null;
    const fresh = !entry.stale && now() - entry.updatedAt < ttlMs;
    return { data: entry.data, updatedAt: entry.updatedAt, fresh };
  };

  const startRequest = (url, errorMessage) => {
    const controller = new AbortController();
    const request = {
      controller,
      consumers: 0,
      promise: null,
    };
    request.promise = (async () => {
      const response = await fetchImpl(url, {
        credentials: 'same-origin',
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(await readErrorDetail(response, errorMessage));
      const payload = await response.json();
      if (!controller.signal.aborted) remember(url, payload);
      return payload;
    })().finally(() => {
      if (inflight.get(url) === request) inflight.delete(url);
    });
    // Evita "unhandled rejection" quando todos os consumidores já desistiram.
    request.promise.catch(() => {});
    inflight.set(url, request);
    return request;
  };

  const load = (url, { signal, force = false, errorMessage } = {}) => {
    if (signal?.aborted) return Promise.reject(createAbortError());
    if (!force) {
      const cached = peek(url);
      if (cached?.fresh) return Promise.resolve(cached.data);
    }

    const request = inflight.get(url) || startRequest(url, errorMessage);
    request.consumers += 1;

    return new Promise((resolve, reject) => {
      let settled = false;
      const release = () => {
        if (settled) return false;
        settled = true;
        signal?.removeEventListener('abort', onAbort);
        request.consumers -= 1;
        return true;
      };
      const onAbort = () => {
        if (!release()) return;
        if (request.consumers <= 0) request.controller.abort();
        reject(createAbortError());
      };
      signal?.addEventListener('abort', onAbort, { once: true });
      request.promise.then(
        (data) => { if (release()) resolve(data); },
        (error) => { if (release()) reject(error); },
      );
    });
  };

  const prime = (url, data) => {
    if (!entries.has(url) || entries.get(url).stale) remember(url, data);
  };

  const invalidate = (prefix = '') => {
    entries.forEach((entry, url) => {
      if (url.startsWith(prefix)) entries.set(url, { ...entry, stale: true });
    });
    listeners.forEach((listener) => listener(prefix));
  };

  const clear = () => {
    inflight.forEach((request) => request.controller.abort());
    inflight.clear();
    entries.clear();
  };

  const subscribe = (listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };

  return Object.freeze({ load, peek, prime, invalidate, clear, subscribe });
}

export const panelDataCache = createPanelDataCache();

export const invalidatePanelData = (prefix) => panelDataCache.invalidate(prefix);
export const clearPanelData = () => panelDataCache.clear();
