import React from 'react';
import { useLanguage } from './i18n.jsx';
import { ErrorNotice } from './ui.jsx';

export default function RefreshStatus({ resource, retry = resource.refresh }) {
  const { t } = useLanguage();
  return (
    <>
      {resource.refreshing && <p role="status">{t('Refreshing…')}</p>}
      <ErrorNotice error={resource.refreshError} retry={retry} />
    </>
  );
}
