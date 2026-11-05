// US-19 is available on main. Older deployments can explicitly disable the input.
export const sourceUrlsEnabled = import.meta.env?.VITE_OPPORTUNITY_SOURCE_URLS !== 'false';

export function validSourceUrl(value) {
  if (value == null || value === '') return true;
  if (typeof value !== 'string' || value.length > 2048 || /[\s\\]/u.test(value)) return false;
  if (!/^https?:\/\//i.test(value)) return false;
  try {
    const url = new URL(value);
    return !!url.hostname && !url.username && !url.password;
  } catch {
    return false;
  }
}

export function futureDeadline(value, now = Date.now()) {
  return value == null || value === '' || new Date(value).getTime() > now;
}
