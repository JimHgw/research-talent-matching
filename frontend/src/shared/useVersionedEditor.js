import { useCallback, useEffect, useRef, useState } from 'react';
import { useMutation } from './useMutation.js';
import { usePageGuard } from './hooks.js';
import { accessLost, requiresReconciliation, uncertainWrite } from './editor-state.js';

const empty = { saved: null, content: null, latest: null, failure: null, unavailable: null };

// Saved revision, editable values and the comparison are independent snapshots.
// A read may replace the draft only while clean or after an explicit reload decision.
export function useVersionedEditor({ read, validate, values, onDirty, onPending }) {
  const [state, setState] = useState(empty);
  const current = useRef(state);
  const alive = useRef(false);
  const reading = useRef(null);
  const [readState, setReadState] = useState({ loading: true, blocking: false, error: null });
  const mutation = useMutation();
  const update = useCallback((change) => {
    if (!alive.current) return;
    current.current = change(current.current);
    setState(current.current);
  }, []);
  const dirtyState = (value) =>
    !!value.saved && JSON.stringify(values(value.saved)) !== JSON.stringify(value.content);
  const needsReviewState = (value) => !!value.failure || !!value.latest;
  const isPending = () => mutation.isPending() || !!reading.current?.blocking;
  function cancelRead() {
    if (reading.current) {
      reading.current.alive = false;
      reading.current.controller.abort();
      reading.current = null;
    }
  }
  function accept(snapshot, keepDraft = false) {
    update((previous) => ({
      ...empty,
      saved: snapshot,
      content: keepDraft ? previous.content : structuredClone(values(snapshot)),
    }));
    mutation.clearError();
  }
  async function load(mode = 'refresh') {
    if (mutation.isPending()) return;
    cancelRead();
    const request = {
      alive: true,
      controller: new AbortController(),
      blocking: mode !== 'refresh',
    };
    reading.current = request;
    setReadState({ loading: true, blocking: request.blocking, error: null });
    try {
      const snapshot = validate(await read({ signal: request.controller.signal }), {
        previous: current.current.saved,
      });
      if (!alive.current || !request.alive) return;
      if (mode === 'compare') update((previous) => ({ ...previous, latest: snapshot }));
      else if (
        mode === 'replace' ||
        (!dirtyState(current.current) && !needsReviewState(current.current))
      )
        accept(snapshot);
      // A draft created while a read was pending cannot acquire that read's revision.
      else update((previous) => ({ ...previous, latest: snapshot }));
      setReadState({ loading: false, blocking: false, error: null });
    } catch (error) {
      if (!alive.current || !request.alive) return;
      if (error.name !== 'AbortError') {
        if (accessLost(error)) update(() => ({ ...empty, unavailable: error }));
        setReadState({ loading: false, blocking: false, error });
      }
    } finally {
      if (reading.current === request) reading.current = null;
    }
  }
  useEffect(() => {
    alive.current = true;
    load();
    const focus = () => {
      if (!isPending() && !dirtyState(current.current) && !needsReviewState(current.current))
        load();
    };
    window.addEventListener('focus', focus);
    return () => {
      alive.current = false;
      cancelRead();
      window.removeEventListener('focus', focus);
    };
  }, [read, validate, values]);

  const dirty = dirtyState(state);
  const needsReview = needsReviewState(state) || readState.error?.code === 'INVALID_RESPONSE';
  const busy = mutation.busy || readState.blocking;
  usePageGuard(dirty || needsReview, busy, onDirty, onPending);
  function change(next) {
    if (isPending() || state.unavailable) return;
    // Invalidates even transports that ignore AbortSignal, before accepting input.
    cancelRead();
    setReadState((previous) => ({ ...previous, loading: false, blocking: false }));
    update((previous) => ({ ...previous, content: next }));
  }
  function write(action, onSuccess, operation) {
    if (isPending() || needsReview || !current.current.saved || current.current.unavailable) return;
    cancelRead();
    setReadState({ loading: false, blocking: false, error: null });
    mutation.clearError();
    const submitted = current.current.saved;
    mutation.run(
      async () =>
        validate(await action(submitted, structuredClone(current.current.content)), {
          previous: submitted,
          operation,
        }),
      (snapshot) => {
        accept(snapshot);
        onSuccess?.(snapshot);
      },
      (error) => {
        if (accessLost(error)) update(() => ({ ...empty, unavailable: error }));
        else if (requiresReconciliation(error))
          update((previous) => ({ ...previous, failure: error }));
      }
    );
  }
  function resolve(useLatest) {
    if (isPending() || !current.current.latest) return;
    accept(current.current.latest, !useLatest);
    setReadState({ loading: false, blocking: false, error: null });
  }
  return {
    ...state,
    dirty,
    needsReview,
    busy,
    isPending,
    change,
    write,
    resolve,
    values,
    loading: !state.saved && readState.loading,
    refreshing: !!state.saved && readState.loading,
    error: state.failure || mutation.error,
    readError: readState.error,
    uncertain: uncertainWrite(state.failure),
    compare: () => {
      if (!isPending()) load('compare');
    },
    reload: () => {
      if (!isPending()) load('replace');
    },
  };
}
