export const opportunityTypes = ['PHD', 'MASTERS', 'RESEARCH_ASSISTANT', 'POSTDOC', 'OTHER'];

// Current Go8 membership: https://go8.edu.au/about. IDs stay stable across labels.
export const go8Universities = [
  { id: 'ADELAIDE', label: 'Adelaide University' },
  { id: 'ANU', label: 'Australian National University' },
  { id: 'MELBOURNE', label: 'University of Melbourne' },
  { id: 'MONASH', label: 'Monash University' },
  { id: 'UNSW', label: 'UNSW Sydney' },
  { id: 'UQ', label: 'University of Queensland' },
  { id: 'USYD', label: 'University of Sydney' },
  { id: 'UWA', label: 'University of Western Australia' },
];

export function localDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export const dateTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;
