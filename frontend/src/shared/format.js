export const displayDate = (value) =>
  new Intl.DateTimeFormat('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(value)
  );
