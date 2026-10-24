export const opportunityTypes = ['PHD', 'MASTERS', 'RESEARCH_ASSISTANT', 'POSTDOC', 'OTHER'];

export function localDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export const dateTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;
