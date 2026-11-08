import { useEffect } from 'react';

export const dataChanged = 'research-workspace-data-changed';

// Only validated server results emit this event. No private content is broadcast.
export function invalidateData(...domains) {
  window.dispatchEvent(new window.CustomEvent(dataChanged, { detail: { domains } }));
}

export function useDataInvalidation(refresh, domains) {
  useEffect(() => {
    const invalidate = (event) => {
      if (event.detail?.domains?.some((domain) => domains.includes(domain))) refresh();
    };
    window.addEventListener(dataChanged, invalidate);
    return () => window.removeEventListener(dataChanged, invalidate);
  }, [refresh, ...domains]);
}
