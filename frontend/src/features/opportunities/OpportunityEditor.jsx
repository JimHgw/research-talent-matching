import React, { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client.js';
import { Badge, Button, ErrorNotice, Field, Notice, Pager } from '../../shared/ui.jsx';
import { useUnsaved } from '../../shared/hooks.js';
import { emptyContent, opportunityFields } from './fields.js';
import RequirementEditor from './RequirementEditor.jsx';
import { OpportunityContent } from './OpportunityDetails.jsx';

export default function OpportunityEditor({ opportunity, tags, onDirty, notify, onBack }) {
  const [saved, setSaved] = useState(opportunity);
  const [content, setContent] = useState(() =>
    structuredClone(opportunity?.content || emptyContent())
  );
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [latest, setLatest] = useState(null);
  const [recent, setRecent] = useState(null);
  const inFlight = useRef(false);
  const baseline = saved?.content || emptyContent();
  const dirty = JSON.stringify(content) !== JSON.stringify(baseline);
  const uncertain =
    ['NETWORK_ERROR', 'INVALID_RESPONSE'].includes(error?.code) || error?.status >= 500;
  const needsReview = error?.code === 'REVISION_CONFLICT' || uncertain;
  useEffect(() => {
    onDirty(dirty || busy);
    return () => onDirty(false);
  }, [dirty, busy, onDirty]);
  useUnsaved(dirty || busy);

  async function run(action) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    try {
      await action();
    } catch (e) {
      setError(e);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  function back() {
    if (!dirty || window.confirm('Discard your unsaved opportunity changes?')) onBack();
  }
  function save(event) {
    event.preventDefault();
    run(async () => {
      setError(null);
      const result = await api.saveOpportunity(saved?.id, saved?.revision, content);
      setSaved(result);
      setContent(structuredClone(result.content));
      setLatest(null);
      notify('Opportunity saved.');
    });
  }
  function publish() {
    run(async () => {
      setError(null);
      const result = await api.publish(saved.id, saved.revision);
      setSaved(result);
      notify('Opportunity published. Signed-in users can now discover it.');
    });
  }
  function reload() {
    run(async () => {
      // Loading for comparison never replaces the form or retries the failed mutation.
      if (saved) setLatest(await api.opportunity(saved.id));
      else setRecent(await api.opportunities('mine'));
    });
  }
  function resolve(useLatest) {
    setSaved(latest);
    if (useLatest) setContent(structuredClone(latest.content));
    setLatest(null);
    setError(null);
  }
  return (
    <div className="opportunity-editor">
      <Button variant="text" onClick={back} disabled={busy}>
        Back to opportunities
      </Button>
      <div className="section-title">
        <h2>{saved ? 'Edit opportunity' : 'Create opportunity'}</h2>
        <Badge status={saved?.status || 'DRAFT'} />
      </div>
      <ErrorNotice error={error} retry={needsReview && !busy ? reload : undefined} />
      {uncertain && (
        <Notice>
          The request may have succeeded. Reload the latest data and check it before trying again.
        </Notice>
      )}
      {latest && (
        <section className="panel" aria-label="Compare opportunity versions">
          <h3>Compare before continuing</h3>
          <p>
            Your input is still here. Review both versions, then choose which content to continue
            editing.
          </p>
          <div className="opportunity-comparison">
            <div>
              <h4>Your local version</h4>
              <OpportunityContent content={content} tags={tags} />
            </div>
            <div>
              <h4>Latest saved version</h4>
              <Badge status={latest.status} />
              <OpportunityContent content={latest.content} tags={tags} />
            </div>
          </div>
          <div className="actions">
            <Button variant="secondary" onClick={() => resolve(true)}>
              Use latest version
            </Button>
            <Button onClick={() => resolve(false)}>Continue editing my version</Button>
          </div>
          <p className="help">
            Continuing with your version does not save it. Review and merge any changes before
            saving again.
          </p>
        </section>
      )}
      {recent && (
        <section className="panel">
          <h3>Recently saved opportunities</h3>
          <p>
            Check whether this draft was created before submitting again. Your form is preserved
            below.
          </p>
          {recent.items.map((item) => (
            <div key={item.id}>
              <OpportunityContent content={item.content} tags={tags} />
              <Button
                variant="secondary"
                onClick={() => {
                  setSaved(item);
                  setContent(structuredClone(item.content));
                  setRecent(null);
                  setError(null);
                }}
              >
                Open saved draft: {item.content.title}
              </Button>
            </div>
          ))}
          <Pager
            data={recent}
            onPage={(page) => run(async () => setRecent(await api.opportunities('mine', page)))}
          />
          <Button
            variant="text"
            onClick={() => {
              setRecent(null);
              setError(null);
            }}
          >
            I checked; keep creating this draft
          </Button>
        </section>
      )}
      <form onSubmit={save}>
        <fieldset disabled={busy} className="opportunity-form-fields">
          <section className="panel">
            <h3>Opportunity details</h3>
            <div className="opportunity-fields">
              {opportunityFields.map(({ key, label, maxLength, multiline }) => (
                <div key={key} className={multiline ? 'opportunity-wide' : undefined}>
                  <Field label={label}>
                    {multiline ? (
                      <textarea
                        required
                        rows={6}
                        maxLength={maxLength}
                        value={content[key]}
                        onChange={(e) => setContent({ ...content, [key]: e.target.value })}
                      />
                    ) : (
                      <input
                        required
                        maxLength={maxLength}
                        value={content[key]}
                        onChange={(e) => setContent({ ...content, [key]: e.target.value })}
                      />
                    )}
                  </Field>
                </div>
              ))}
              <Field label="Discipline group">
                <select
                  value={content.disciplineGroup}
                  onChange={(e) => setContent({ ...content, disciplineGroup: e.target.value })}
                >
                  <option value="STEM">STEM</option>
                  <option value="BUSINESS">BUSINESS</option>
                </select>
              </Field>
            </div>
          </section>
          <section className="panel">
            <RequirementEditor
              value={content.requirements}
              tags={tags}
              onChange={(requirements) => setContent({ ...content, requirements })}
            />
          </section>
          {saved?.status === 'PUBLISHED' ? (
            <Notice>
              Saved changes will be visible immediately. Published opportunities must keep at least
              one requirement.
            </Notice>
          ) : (
            <Notice>
              Drafts are visible only to your team. Save your changes before publishing.
            </Notice>
          )}
          <div className="actions">
            <Button type="submit" disabled={busy || needsReview || (!dirty && !!saved)}>
              {busy ? 'Working…' : saved ? 'Save changes' : 'Save draft'}
            </Button>
            {saved?.status === 'DRAFT' && (
              <Button
                variant="secondary"
                onClick={publish}
                disabled={busy || dirty || needsReview || !saved.content.requirements.length}
              >
                Publish opportunity
              </Button>
            )}
          </div>
        </fieldset>
      </form>
    </div>
  );
}
