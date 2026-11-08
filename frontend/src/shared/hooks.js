import { useCallback, useEffect, useRef, useState } from 'react';

// Each workspace callback combines the active guards of its mounted callers.
const activeGuards = new WeakMap();

function reportGuard(callback, owner, active) {
  if (!callback) return;
  const owners = activeGuards.get(callback) || new Set();
  if (active) owners.add(owner);
  else owners.delete(owner);
  if (owners.size) activeGuards.set(callback, owners);
  else activeGuards.delete(callback);
  callback(owners.size > 0);
}

const sameContext = (left, right) =>
  left.length === right.length && left.every((value, index) => Object.is(value, right[index]));
const emptyResource = { data: null, loading: true, error: null, refreshError: null };

// Retention is opt-in: editors keep their existing explicit reload/draft contract.
// `loading` still means any request; read-only views opt into `initialLoading`.
export function useResource(
  loader,
  dependencies = [],
  focusRefresh = false,
  { retainData = false } = {}
) {
  const [state, setState] = useState({ ...emptyResource, context: dependencies });
  const [version, setVersion] = useState(0);
  const active = useRef(null);
  const refresh = useCallback(() => {
    // Invalidate immediately, including transports that ignore abort.
    if (active.current) {
      active.current.alive = false;
      active.current.controller.abort();
    }
    setVersion((value) => value + 1);
  }, []);
  useEffect(() => {
    const request = { alive: true, controller: new AbortController() };
    active.current = request;
    setState((previous) => ({
      ...emptyResource,
      context: dependencies,
      data: retainData && sameContext(previous.context, dependencies) ? previous.data : null,
    }));
    Promise.resolve()
      .then(() => {
        if (request.alive) return loader({ signal: request.controller.signal });
      })
      .then(
        (data) => {
          if (request.alive)
            setState({
              data,
              loading: false,
              error: null,
              refreshError: null,
              context: dependencies,
            });
        },
        (error) => {
          if (!request.alive) return;
          setState((previous) => {
            if (error.name === 'AbortError')
              return { ...previous, loading: previous.data === null };
            // Only transport/temporary service failures may retain an authorised snapshot.
            // Permission, eligibility, missing-resource and invalid-response failures clear it.
            const recoverable =
              error.code !== 'INVALID_RESPONSE' &&
              error.code !== 'PROFILE_UNCONFIRMED' &&
              (error.status === 0 || error.status === 429 || error.status >= 500);
            if (retainData && previous.data !== null && recoverable)
              return { ...previous, loading: false, error: null, refreshError: error };
            return { ...emptyResource, loading: false, error, context: dependencies };
          });
        }
      );
    return () => {
      request.alive = false;
      request.controller.abort();
      if (active.current === request) active.current = null;
    };
  }, [...dependencies, version, retainData]);
  useEffect(() => {
    if (!focusRefresh) return;
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [focusRefresh, refresh]);
  // Do not render old-context content even for the render before effect cleanup.
  const current = sameContext(state.context, dependencies) ? state : emptyResource;
  return {
    ...current,
    initialLoading: current.loading && current.data === null,
    refreshing: current.loading && current.data !== null,
    refresh,
  };
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
  const owner = useRef({}).current;
  useUnsaved(dirty || busy);
  useEffect(() => {
    reportGuard(onDirty, owner, dirty || busy);
    reportGuard(onPending, owner, busy);
    return () => {
      reportGuard(onDirty, owner, false);
      reportGuard(onPending, owner, false);
    };
  }, [dirty, busy, onDirty, onPending, owner]);
}
