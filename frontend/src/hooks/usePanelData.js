import { useCallback, useEffect, useRef, useState } from 'react';
import { isAbortError, panelDataCache } from '../services/panelDataCache';

export const PANEL_FILTER_DEBOUNCE_MS = 250;

// Carrega um endpoint GET de painel com cache por URL, cancelamento e debounce.
//
// - Primeira carga: sem debounce; `isInitialLoading` fica true até chegar algo.
// - Troca de filtros (URL): espera `debounceMs`, mantém os dados anteriores na
//   tela e expõe `isRefreshing` para um indicador discreto.
// - URL já em cache e fresca: aparece na hora, sem requisição.
// - `refresh()` ignora o cache; invalidações externas revalidam em segundo plano.
export function usePanelData(url, {
  debounceMs = PANEL_FILTER_DEBOUNCE_MS,
  errorMessage,
  cache = panelDataCache,
} = {}) {
  const [state, setState] = useState(() => {
    const initial = url ? cache.peek(url) : null;
    return {
      data: initial?.data ?? null,
      error: null,
      fetching: Boolean(url) && !initial?.fresh,
    };
  });
  const controllerRef = useRef(null);
  const mountedUrlRef = useRef(null);
  const errorMessageRef = useRef(errorMessage);
  errorMessageRef.current = errorMessage;
  const hasDataRef = useRef(state.data !== null);
  hasDataRef.current = state.data !== null;

  const run = useCallback((targetUrl, { force = false } = {}) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState((current) => (current.fetching && !current.error
      ? current
      : { ...current, error: null, fetching: true }));
    cache.load(targetUrl, {
      signal: controller.signal,
      force,
      errorMessage: errorMessageRef.current,
    }).then(
      (data) => {
        if (controller.signal.aborted) return;
        setState({ data, error: null, fetching: false });
      },
      (error) => {
        if (controller.signal.aborted || isAbortError(error)) return;
        setState((current) => ({
          ...current,
          error: error?.message || errorMessageRef.current || 'Erro ao carregar dados.',
          fetching: false,
        }));
      },
    );
    return controller;
  }, [cache]);

  useEffect(() => {
    if (!url) return undefined;
    mountedUrlRef.current = url;
    const cached = cache.peek(url);
    if (cached) {
      setState((current) => (
        current.data === cached.data && current.fetching === !cached.fresh && !current.error
          ? current
          : { data: cached.data, error: null, fetching: !cached.fresh }
      ));
    }
    if (cached?.fresh) return undefined;

    // Sem dados na tela ainda: busca já. Com dados: espera o usuário terminar
    // de mexer nos filtros antes de disparar a requisição.
    if (!hasDataRef.current || debounceMs <= 0) {
      const controller = run(url);
      return () => controller.abort();
    }

    setState((current) => (current.fetching ? current : { ...current, fetching: true }));
    let controller = null;
    const timer = setTimeout(() => { controller = run(url); }, debounceMs);
    return () => {
      clearTimeout(timer);
      controller?.abort();
    };
  }, [cache, debounceMs, run, url]);

  useEffect(() => cache.subscribe((prefix) => {
    const current = mountedUrlRef.current;
    if (current && current.startsWith(prefix)) run(current);
  }), [cache, run]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const refresh = useCallback(() => {
    if (url) run(url, { force: true });
  }, [run, url]);

  return {
    data: state.data,
    error: state.error,
    isInitialLoading: state.fetching && state.data === null,
    isRefreshing: state.fetching && state.data !== null,
    isFetching: state.fetching,
    refresh,
  };
}
