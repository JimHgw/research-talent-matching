import { useCallback, useEffect, useRef, useState } from 'react';

// Writes are not aborted on unmount: the server may already have committed them.
// Only the still-mounted caller receives the result or runs its UI callbacks.
export function useMutation() {
  const mounted = useRef(true);
  const pending = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const isPending = useCallback(() => pending.current, []);
  const clearError = useCallback(() => setError(null), []);
  const run = useCallback(async (action, onSuccess, onFailure) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    try {
      const result = await action();
      if (mounted.current) onSuccess?.(result);
    } catch (failure) {
      if (mounted.current) {
        setError(failure);
        onFailure?.(failure);
      }
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }, []);
  return { busy, error, setError, clearError, run, isPending };
}
