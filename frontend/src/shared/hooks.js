import { useEffect, useState } from 'react';

export function useResource(loader, dependencies = [], focusRefresh = false) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let alive = true;
    setState({ data: null, loading: true, error: null });
    Promise.resolve()
      .then(loader)
      .then(
        (data) => {
          if (alive) setState({ data, loading: false, error: null });
        },
        (error) => {
          if (alive) setState({ data: null, loading: false, error });
        }
      );
    return () => {
      alive = false;
    };
  }, [...dependencies, version]);
  useEffect(() => {
    if (!focusRefresh) return;
    const refresh = () => setVersion((v) => v + 1);
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [focusRefresh]);
  return { ...state, refresh: () => setVersion((v) => v + 1) };
}
export function useUnsaved(dirty) {
  useEffect(() => {
    if (!dirty) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);
}

export function usePageGuard(dirty, busy, onDirty, onPending) {
  useUnsaved(dirty || busy);
  useEffect(() => {
    onDirty?.(dirty || busy);
    onPending?.(busy);
    return () => {
      onDirty?.(false);
      onPending?.(false);
    };
  }, [dirty, busy, onDirty, onPending]);
}
