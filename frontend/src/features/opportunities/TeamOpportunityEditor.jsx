import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { useUnsaved } from '../../shared/hooks.js';
import { Button, ErrorNotice, Field, Icon, Modal } from '../../shared/ui.jsx';
const freshOpportunity = () => ({
  title: '',
  university: '',
  disciplineGroup: 'STEM',
  discipline: '',
  researchArea: '',
  description: '',
  requirements: [],
});

export default function OpportunityEditor({ opportunity, tags, onClose, onSaved, onDirty }) {
  const [record, setRecord] = useState(opportunity);
  const [baseline, setBaseline] = useState(() =>
    structuredClone(opportunity?.content || freshOpportunity())
  );
  const [content, setContent] = useState(() =>
    structuredClone(opportunity?.content || freshOpportunity())
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [pendingAction, setPendingAction] = useState(null);
  const dirty = JSON.stringify(content) !== JSON.stringify(baseline);
  useUnsaved(dirty);
  useEffect(() => {
    onDirty?.(dirty);
    return () => onDirty?.(false);
  }, [dirty, onDirty]);
  function close() {
    if (busy) return;
    if (dirty) setPendingAction('close');
    else onClose();
  }
  async function reload() {
    setPendingAction(null);
    setBusy(true);
    try {
      const latest = await api.opportunity(record.id);
      setRecord(latest);
      setBaseline(structuredClone(latest.content));
      setContent(structuredClone(latest.content));
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  function set(key, value) {
    setContent((current) => ({ ...current, [key]: value }));
  }

  function updateReq(index, changes) {
    const requirements = content.requirements.map((requirement, currentIndex) => {
      if (currentIndex === index) {
        return { ...requirement, ...changes };
      }
      return requirement;
    });
    set('requirements', requirements);
  }

  function validateForm() {
    const requiredFields = ['title', 'university', 'discipline', 'researchArea', 'description'];
    for (const field of requiredFields) {
      if (!content[field].trim()) {
        return 'Complete all required fields with non-blank text.';
      }
    }

    for (let index = 0; index < content.requirements.length; index++) {
      const requirement = content.requirements[index];
      const hasInvalidTag = requirement.tagIds.some((id) => {
        return !tags.some((tag) => tag.id === id && tag.kind === requirement.kind);
      });
      if (
        !requirement.label.trim() ||
        requirement.tagIds.length === 0 ||
        requirement.tagIds.length > 20 ||
        hasInvalidTag
      ) {
        return `Requirement ${index + 1} needs a label and 1-20 valid tags.`;
      }
    }

    if (record?.status === 'PUBLISHED' && content.requirements.length === 0) {
      return 'Published opportunities need at least one requirement.';
    }
    return null;
  }

  async function save(e) {
    e.preventDefault();
    if (busy) return;
    const validationError = validateForm();
    if (validationError) {
      setError({ message: validationError });
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api.saveOpportunity(record?.id, record?.revision, content);
      onSaved(saved);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={record ? 'Edit research opportunity' : 'Create research opportunity'}
      onClose={close}
    >
      {pendingAction ? (
        <div className="editor-confirm" role="alert">
          <h3>
            {pendingAction === 'reload' ? 'Reload the latest version?' : 'Leave without saving?'}
          </h3>
          <p>Your unsaved opportunity changes will be discarded.</p>
          <div className="actions">
            <Button variant="secondary" onClick={() => setPendingAction(null)}>
              Keep editing
            </Button>
            <Button onClick={() => (pendingAction === 'reload' ? reload() : onClose())}>
              {pendingAction === 'reload' ? 'Discard and reload' : 'Discard changes'}
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={save}>
          <ErrorNotice
            error={error}
            retry={
              error?.code === 'REVISION_CONFLICT' ? () => setPendingAction('reload') : undefined
            }
          />
          <fieldset className="team-opportunity-fields" disabled={busy}>
            {dirty && (
              <span className="editor-dirty" role="status">
                Unsaved changes
              </span>
            )}
            <div className="form-grid">
              {[
                ['title', 'Opportunity title'],
                ['university', 'University'],
                ['discipline', 'Discipline'],
                ['researchArea', 'Research area'],
              ].map(([key, label]) => (
                <Field key={key} label={`${label} *`}>
                  <input
                    value={content[key]}
                    required
                    maxLength={key === 'researchArea' ? 300 : 200}
                    onChange={(e) => set(key, e.target.value)}
                  />
                </Field>
              ))}
              <Field label="Discipline group">
                <select
                  value={content.disciplineGroup}
                  onChange={(e) => set('disciplineGroup', e.target.value)}
                >
                  <option value="STEM">STEM</option>
                  <option value="BUSINESS">Business</option>
                </select>
              </Field>
            </div>
            <Field label="Description *">
              <textarea
                rows={4}
                value={content.description}
                required
                maxLength={10000}
                onChange={(e) => set('description', e.target.value)}
              />
            </Field>
            <div className="section-title">
              <div>
                <h3>What does your project need?</h3>
                <p>Tags in the same requirement must all be supported for a full match.</p>
              </div>
            </div>
            {content.requirements.map((r, i) => (
              <section className="record" key={r.id}>
                <div className="record-heading">
                  <strong>Requirement {i + 1}</strong>
                  <Button
                    variant="icon"
                    aria-label={`Remove requirement ${i + 1}`}
                    onClick={() =>
                      set(
                        'requirements',
                        content.requirements.filter((_, n) => n !== i)
                      )
                    }
                  >
                    <Icon name="close" />
                  </Button>
                </div>
                <Field label="Requirement label *">
                  <input
                    required
                    maxLength={300}
                    value={r.label}
                    onChange={(e) => updateReq(i, { label: e.target.value })}
                  />
                </Field>
                <div className="form-grid">
                  <Field label="Category">
                    <select
                      value={r.kind}
                      onChange={(e) => updateReq(i, { kind: e.target.value, tagIds: [] })}
                    >
                      <option value="SKILL">Skill</option>
                      <option value="INTEREST">Research interest</option>
                    </select>
                  </Field>
                  <Field label="Importance">
                    <select
                      value={r.importance}
                      onChange={(e) => updateReq(i, { importance: e.target.value })}
                    >
                      <option value="REQUIRED">Required</option>
                      <option value="PREFERRED">Preferred</option>
                    </select>
                  </Field>
                </div>
                <div className="tag-options">
                  {tags
                    .filter((t) => t.kind === r.kind)
                    .map((t) => (
                      <label
                        className={`tag-option ${r.tagIds.includes(t.id) ? 'selected' : ''}`}
                        key={t.id}
                      >
                        <input
                          type="checkbox"
                          checked={r.tagIds.includes(t.id)}
                          onChange={(e) =>
                            updateReq(i, {
                              tagIds: e.target.checked
                                ? [...r.tagIds, t.id]
                                : r.tagIds.filter((id) => id !== t.id),
                            })
                          }
                        />
                        {t.label}
                      </label>
                    ))}
                </div>
              </section>
            ))}
            <Button
              variant="secondary"
              disabled={content.requirements.length >= 50}
              onClick={() =>
                set('requirements', [
                  ...content.requirements,
                  {
                    id: `req_${crypto.randomUUID()}`,
                    label: '',
                    kind: 'SKILL',
                    importance: 'REQUIRED',
                    tagIds: [],
                  },
                ])
              }
            >
              <Icon name="plus" size={16} />
              Add requirement
            </Button>
            <p className="help">
              {record?.status === 'PUBLISHED'
                ? 'Saving updates this published opportunity immediately.'
                : 'Save a draft first. Publish it when its requirements are ready.'}
            </p>
            <div className="actions">
              <Button variant="secondary" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" disabled={busy || (!!record && !dirty)}>
                {busy ? 'Saving…' : record ? 'Save opportunity' : 'Save draft'}
              </Button>
            </div>
          </fieldset>
        </form>
      )}
    </Modal>
  );
}
