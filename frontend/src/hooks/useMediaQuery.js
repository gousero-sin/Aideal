import { useCallback, useSyncExternalStore } from 'react';

const getMatcher = (query) => (
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia(query)
    : null
);

// Assina uma media query CSS e devolve se ela casa agora.
export function useMediaQuery(query, serverValue = false) {
  const subscribe = useCallback((onChange) => {
    const matcher = getMatcher(query);
    if (!matcher) return () => {};
    matcher.addEventListener('change', onChange);
    return () => matcher.removeEventListener('change', onChange);
  }, [query]);
  const getSnapshot = useCallback(() => getMatcher(query)?.matches ?? serverValue, [query, serverValue]);
  return useSyncExternalStore(subscribe, getSnapshot, () => serverValue);
}
