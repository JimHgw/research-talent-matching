import { api } from '../../api/client.js';
import { useVersionedEditor } from '../../shared/useVersionedEditor.js';
import { invalidateData } from '../../shared/data-invalidation.js';
import { privacyValues, validatePrivacy } from './privacy-state.js';

export function usePrivacyEditor({ onDirty, onPending, notify, confirmDiscard, repository = api }) {
  const editor = useVersionedEditor({
    read: repository.privacy,
    validate: validatePrivacy,
    values: privacyValues,
    onDirty,
    onPending,
  });
  return {
    ...editor,
    change: (value) => editor.change({ ...value, visibleFields: [...value.visibleFields].sort() }),
    refresh: () => {
      if (editor.isPending() || (editor.dirty && !confirmDiscard())) return;
      editor.reload();
    },
    save: () => {
      if (!editor.dirty) return;
      editor.write(
        (saved, value) => repository.savePrivacy({ expectedRevision: saved.revision, ...value }),
        () => {
          invalidateData('privacy', 'matching', 'collections');
          notify('Privacy settings saved. Future team results use these choices.');
        },
        'save'
      );
    },
  };
}
