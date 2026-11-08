import { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { useVersionedEditor } from '../../shared/useVersionedEditor.js';
import { invalidateData } from '../../shared/data-invalidation.js';
import { profileValues, validateProfile } from './profile-state.js';

export function useProfileEditor({ onDirty, onPending, notify, confirmDiscard, repository = api }) {
  const editor = useVersionedEditor({
    read: repository.profile,
    validate: validateProfile,
    values: profileValues,
    onDirty,
    onPending,
  });
  const [acknowledged, setAcknowledged] = useState(null);
  useEffect(() => {
    if (editor.unavailable) setAcknowledged(null);
  }, [editor.unavailable]);
  const reviewed = !!editor.saved && acknowledged === editor.saved;
  const confirmed =
    editor.saved?.confirmation.status === 'CONFIRMED' &&
    editor.saved.confirmation.confirmedRevision === editor.saved.revision;
  function refresh() {
    if (editor.isPending() || (editor.dirty && !confirmDiscard())) return;
    setAcknowledged(null);
    editor.reload();
  }
  function save(event) {
    event.preventDefault();
    if (!editor.dirty) return;
    editor.write(
      (saved, content) => repository.saveProfile(saved.revision, content),
      () => {
        setAcknowledged(null);
        invalidateData('profile', 'matching', 'collections');
        notify('Profile saved. Review and confirm to use the latest information.');
      },
      'save'
    );
  }
  function confirm() {
    if (editor.dirty || !reviewed) return;
    editor.write(
      (saved) => repository.confirm(saved.revision),
      () => {
        setAcknowledged(null);
        invalidateData('profile', 'matching', 'collections');
        notify('Profile confirmed. Your recommendations are ready.');
      },
      'confirm'
    );
  }
  return {
    ...editor,
    profile: editor.saved,
    confirmed,
    reviewed,
    refresh,
    save,
    confirm,
    change: (next) => {
      if (!editor.isPending()) {
        setAcknowledged(null);
        editor.change(next);
      }
    },
    setReviewed: (value) =>
      setAcknowledged(value && !editor.dirty && !editor.needsReview ? editor.saved : null),
    resolve: (latest) => {
      setAcknowledged(null);
      editor.resolve(latest);
    },
  };
}
