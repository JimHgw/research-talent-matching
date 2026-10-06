import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { Button, ErrorNotice, Loading, Modal, Notice } from '../../shared/ui.jsx';
import { useResource } from '../../shared/hooks.js';
import { labels } from '../../shared/profile-labels.js';
import ProfileFields from '../profile/ProfileFields.jsx';

export default function ExtractionReview({ document, tags, onClose, onApplied }) {
  const resource = useResource(
    () => Promise.all([api.extraction(document.id), api.profile()]),
    [document.id]
  );
  const [sections, setSections] = useState(null);
  const [selected, setSelected] = useState([]);
  const [ack, setAck] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (resource.data) {
      const s = resource.data[0].suggestedSections;
      setSections(structuredClone(s));
      setSelected(Object.keys(s));
    }
  }, [resource.data]);
  async function apply(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.apply(
        document.id,
        resource.data[1].revision,
        Object.fromEntries(selected.map((key) => [key, sections[key]]))
      );
      onApplied();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Review extraction suggestions" onClose={onClose}>
      {resource.loading || (!sections && !resource.error) ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : (
        <form onSubmit={apply}>
          <Notice>{resource.data[0].warnings.join(' ')}</Notice>
          <p>Choose the sections to import. Edit any suggestion below before applying it.</p>
          <div className="tag-options">
            {Object.keys(sections).map((key) => (
              <label className="tag-option" key={key}>
                <input
                  type="checkbox"
                  checked={selected.includes(key)}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked ? [...selected, key] : selected.filter((k) => k !== key)
                    )
                  }
                />
                {labels[key]}
              </label>
            ))}
          </div>
          <ProfileFields
            content={sections}
            onChange={setSections}
            tags={tags}
            identity={false}
            sections={selected}
          />
          {resource.data[0].uncertainFields.map((f, i) => (
            <p className="help" key={i}>
              {labels[f.field]}: {f.status.replaceAll('_', ' ')} — {f.reason}
            </p>
          ))}
          <ErrorNotice error={error} />
          <label className="check-label">
            <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />I
            understand that importing replaces the selected sections in my profile and requires a
            separate confirmation.
          </label>
          <div className="actions">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy || !ack || !selected.length}>
              {busy ? 'Importing…' : 'Apply reviewed sections'}
            </Button>
          </div>
          {error?.code === 'REVISION_CONFLICT' && (
            <p className="help">
              Your profile changed while this review was open. Close this dialog and review the
              latest profile before reopening extraction.
            </p>
          )}
        </form>
      )}
    </Modal>
  );
}
