export const displayDate = (value, language = 'en') =>
  new Intl.DateTimeFormat(language === 'en' ? 'en-AU' : language, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));
