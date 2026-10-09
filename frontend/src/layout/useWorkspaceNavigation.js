import { useState } from 'react';
import { api } from '../api/client.js';
import { useMutation } from '../shared/useMutation.js';

export function useWorkspaceNavigation(definition, onLogout, closeMenu) {
  const [page, setPage] = useState(definition.defaultPage);
  const [pageContext, setPageContext] = useState({});
  const [dirty, setDirty] = useState(false);
  const [writePending, setWritePending] = useState(false);
  const [pending, setPending] = useState(null);
  const logout = useMutation();
  const busy = writePending || logout.busy;
  function go(target, context = {}) {
    if (target === 'logout') {
      logout.clearError();
      logout.run(api.logout, onLogout);
      return;
    }
    if (!definition.pages[target]) return;
    setDirty(false);
    setPageContext(context);
    setPage(target);
    closeMenu();
    window.scrollTo({ top: 0 });
  }
  function navigate(target, context = {}) {
    if (target === page && !Object.keys(context).length) {
      closeMenu();
      return;
    }
    if (dirty || busy || logout.isPending()) setPending({ target, context });
    else go(target, context);
  }
  function discard() {
    if (busy || logout.isPending()) return;
    const next = pending;
    setPending(null);
    setDirty(false);
    go(next.target, next.context);
  }
  return {
    page,
    pageContext,
    navigate,
    onDirty: setDirty,
    onPending: setWritePending,
    pending,
    cancel: () => setPending(null),
    discard,
    busy,
    logoutError: logout.error,
  };
}
