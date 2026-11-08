import React from 'react';
import { useLanguage } from './i18n.jsx';
import { Button, ErrorNotice, Notice } from './ui.jsx';

export default function EditorRecovery({ editor, renderVersion }) {
  const { t } = useLanguage();
  return (
    <>
      <ErrorNotice
        error={editor.error}
        retry={editor.needsReview && !editor.busy ? editor.refresh : undefined}
      />
      <ErrorNotice error={editor.readError} retry={!editor.busy ? editor.refresh : undefined} />
      {editor.refreshing && <p role="status">{t('Refreshing…')}</p>}
      {editor.uncertain && (
        <Notice>
          {t(
            'The request may have succeeded. Reload the latest data and check it before trying again.'
          )}
        </Notice>
      )}
      {editor.needsReview && !editor.latest && (
        <Button variant="secondary" disabled={editor.busy} onClick={editor.compare}>
          {t('Compare before continuing')}
        </Button>
      )}
      {editor.latest && (
        <section className="panel" aria-label={t('Compare before continuing')}>
          <h3>{t('Compare before continuing')}</h3>
          <p>
            {t(
              'Your input is still here. Review both versions, then choose which content to continue editing.'
            )}
          </p>
          <div className="opportunity-comparison">
            <div>
              <h4>{t('Your local version')}</h4>
              {renderVersion(editor.content)}
            </div>
            <div>
              <h4>{t('Latest saved version')}</h4>
              {renderVersion(editor.values(editor.latest))}
            </div>
          </div>
          <div className="actions">
            <Button variant="secondary" disabled={editor.busy} onClick={() => editor.resolve(true)}>
              {t('Use latest version')}
            </Button>
            <Button disabled={editor.busy} onClick={() => editor.resolve(false)}>
              {t('Continue editing my version')}
            </Button>
          </div>
          <p className="help">
            {t(
              'Continuing with your version does not save it. Review and merge any changes before saving again.'
            )}
          </p>
        </section>
      )}
    </>
  );
}
