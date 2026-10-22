import React from 'react';
import { Button, ErrorNotice, Notice } from '../../shared/ui.jsx';

export default function ReviewRecovery({ error, empty, retry, onManual, onRefresh, onClose }) {
  const waiting = error?.code === 'EXTRACTION_NOT_READY';
  const failed = error?.code === 'EXTRACTION_FAILED';
  const unavailable = [401, 403, 404].includes(error?.status);
  return (
    <>
      <ErrorNotice error={error} />
      <Notice>
        {empty
          ? 'No structured suggestions were found. You can enter your information manually; your saved profile has not changed.'
          : waiting
            ? 'This document is still being processed. Check again later or continue with manual entry.'
            : failed
              ? 'The document could not be processed. Upload another PDF or DOCX, or enter your information manually.'
              : unavailable
                ? 'This document is no longer available to this account. Refresh the document list.'
                : 'Suggestions could not be loaded safely. Reload them or continue with manual entry.'}
      </Notice>
      <div className="actions">
        {!empty && !failed && !unavailable && (
          <Button onClick={retry}>{waiting ? 'Check again' : 'Reload suggestions'}</Button>
        )}
        {failed && (
          <Button variant="secondary" onClick={onClose}>
            Upload another document
          </Button>
        )}
        {!empty && (
          <Button variant="secondary" onClick={onRefresh}>
            Refresh document status
          </Button>
        )}
        <Button variant="text" onClick={onManual}>
          Continue with manual entry
        </Button>
      </div>
    </>
  );
}
