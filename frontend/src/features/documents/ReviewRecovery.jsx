import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { Button, ErrorNotice, Notice } from '../../shared/ui.jsx';

export default function ReviewRecovery({ error, empty, retry, onManual, onRefresh, onClose }) {
  const { t } = useLanguage();
  const waiting = error?.code === 'EXTRACTION_NOT_READY';
  const failed = error?.code === 'EXTRACTION_FAILED';
  const unavailable = [401, 403, 404].includes(error?.status);
  return (
    <>
      <ErrorNotice error={error} />
      <Notice>
        {empty
          ? t(
              'No structured suggestions were found. You can enter your information manually; your saved profile has not changed.'
            )
          : waiting
            ? t(
                'This document is still being processed. Check again later or continue with manual entry.'
              )
            : failed
              ? t(
                  'The document could not be processed. Upload another PDF or DOCX, or enter your information manually.'
                )
              : unavailable
                ? t(
                    'This document is no longer available to this account. Refresh the document list.'
                  )
                : t(
                    'Suggestions could not be loaded safely. Reload them or continue with manual entry.'
                  )}
      </Notice>
      <div className="actions">
        {!empty && !failed && !unavailable && (
          <Button onClick={retry}>{waiting ? t('Check again') : t('Reload suggestions')}</Button>
        )}
        {failed && (
          <Button variant="secondary" onClick={onClose}>
            {t('Upload another document')}
          </Button>
        )}
        {!empty && (
          <Button variant="secondary" onClick={onRefresh}>
            {t('Refresh document status')}
          </Button>
        )}
        <Button variant="text" onClick={onManual}>
          {t('Continue with manual entry')}
        </Button>
      </div>
    </>
  );
}
