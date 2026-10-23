import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client.js';

// Revalidate the server-owned identity when returning to a tab. Late responses from
// an earlier login/logout must never restore a previous account's workspace.
export function useAccountSession() {
  const [session, setSession] = useState({ user: null, loading: true, error: null });
  const generation = useRef(0);
  const alive = useRef(false);
  const accept = useCallback((user) => {
    generation.current++;
    setSession({ user, loading: false, error: null });
  }, []);
  const refresh = useCallback(async () => {
    const request = ++generation.current;
    try {
      const current = await api.session();
      if (alive.current && request === generation.current)
        setSession({ user: current.user, loading: false, error: null });
    } catch (error) {
      if (alive.current && request === generation.current)
        setSession({ user: null, loading: false, error });
    }
  }, []);
  const signedOut = useCallback(() => {
    // Logout clears the cookie and CSRF token. Bootstrap the anonymous session
    // before allowing another login, registration or password-reset request.
    setSession({ user: null, loading: true, error: null });
    return refresh();
  }, [refresh]);
  useEffect(() => {
    alive.current = true;
    refresh();
    window.addEventListener('focus', refresh);
    return () => {
      alive.current = false;
      generation.current++;
      window.removeEventListener('focus', refresh);
    };
  }, [refresh]);
  return { ...session, accept, refresh, signedOut };
}
