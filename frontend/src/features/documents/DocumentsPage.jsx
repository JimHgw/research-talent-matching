import React, { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client.js';
import {
  Badge,
  Button,
  Empty,
  ErrorNotice,
  Field,
  Icon,
  Loading,
  Notice,
  Pager,
} from '../../shared/ui.jsx';
import { useResource, usePageGuard } from '../../shared/hooks.js';
import { useMutation } from '../../shared/useMutation.js';
import { displayDate } from '../../shared/format.js';
import ExtractionReview from './ExtractionReview.jsx';

export default function DocumentsPage({ tags, notify, navigate, onDirty, onPending }) {
  const [page, setPage] = useState(1);
  const resource = useResource(() => api.documents(page), [page]);
  const [file, setFile] = useState(null);
  const [kind, setKind] = useState('CV');
  const { busy, error, setError, clearError, run, isPending } = useMutation();
  const [selected, setSelected] = useState(null);
  const [paused, setPaused] = useState(false);
  const input = useRef();
  const started = useRef(Date.now());
  const pending = resource.data?.items.some((d) => ['QUEUED', 'PROCESSING'].includes(d.status));
  usePageGuard(false, busy, onDirty, onPending);
  useEffect(() => {
    if (!pending || paused) return;
    const timer = setInterval(() => {
      if (Date.now() - started.current >= 60000) setPaused(true);
      else resource.refresh();
    }, 2000);
    return () => clearInterval(timer);
  }, [pending, paused, resource.data]);
  function upload(e) {
    e.preventDefault();
    if (isPending() || !file) return;
    clearError();
    run(
      () => api.upload(file, kind),
      () => {
        setFile(null);
        if (input.current) input.current.value = '';
        setPage(1);
        started.current = Date.now();
        setPaused(false);
        resource.refresh();
        notify('Document received. Processing status will update automatically.');
      }
    );
  }
  async function download(d) {
    try {
      const blob = await api.download(d.id);
      const url = URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = d.fileName;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e);
    }
  }
  return (
    <>
      <div className="section-title">
        <div>
          <h2>A head start for your profile</h2>
          <p>Upload a document, review its suggestions, then choose what to keep.</p>
        </div>
        <Button variant="secondary" onClick={() => navigate('profile')}>
          Enter details manually
        </Button>
      </div>
      <ErrorNotice error={error} />
      <form className="panel upload-panel" onSubmit={upload}>
        <span className="upload-icon">
          <Icon name="upload" size={32} />
        </span>
        <h3>Add your CV or transcript</h3>
        <p className="muted">PDF or DOCX · Up to 10 MiB · Always private</p>
        <fieldset className="form-fields upload-controls" disabled={busy}>
          <Field label="Document type">
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="CV">CV / Resume</option>
              <option value="TRANSCRIPT">Academic transcript</option>
            </select>
          </Field>
          <Field label="Choose a document">
            <input
              ref={input}
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setFile(e.target.files[0] || null)}
              required
            />
          </Field>
          <Button type="submit" disabled={busy || !file}>
            {busy ? 'Uploading…' : 'Upload document'}
            <Icon name="upload" size={16} />
          </Button>
        </fieldset>
      </form>
      <div className="section-title">
        <h2>Your documents</h2>
        <Button
          variant="text"
          onClick={() => {
            started.current = Date.now();
            setPaused(false);
            resource.refresh();
          }}
        >
          Refresh status
        </Button>
      </div>
      {paused && (
        <Notice>
          Automatic checks paused after 60 seconds. Refresh to check again, or continue with manual
          entry.
        </Notice>
      )}
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : !resource.data.items.length ? (
        <Empty icon="file" title="No documents yet">
          Uploading is optional. You can build your entire profile manually.
        </Empty>
      ) : (
        <div className="document-list">
          {resource.data.items.map((d) => (
            <article className="panel document-row" key={d.id}>
              <span className="file-icon">
                <Icon name="file" size={25} />
              </span>
              <div className="document-name">
                <h3>{d.fileName}</h3>
                <p>
                  {d.kind} · {(d.sizeBytes / 1024).toFixed(1)} KB · {displayDate(d.createdAt)}
                </p>
                {d.error && <p className="error-text">{d.error.message}</p>}
                {['QUEUED', 'PROCESSING'].includes(d.status) && (
                  <p className="help" role="status">
                    {d.status === 'QUEUED'
                      ? 'Waiting for document processing.'
                      : 'Extracting suggestions. Review will be available when processing finishes.'}
                  </p>
                )}
              </div>
              <Badge status={d.status} />
              <div className="document-actions">
                <Button variant="text" onClick={() => download(d)}>
                  Download
                </Button>
                {d.status === 'READY' && (
                  <Button variant="secondary" onClick={() => setSelected(d)}>
                    Review suggestions
                  </Button>
                )}
                {d.status === 'FAILED' && (
                  <Button variant="secondary" onClick={() => navigate('profile')}>
                    Enter manually
                  </Button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      <Pager data={resource.data} onPage={setPage} />
      {selected && (
        <ExtractionReview
          key={selected.id}
          onDirty={onDirty}
          onPending={onPending}
          document={selected}
          tags={tags}
          onClose={() => setSelected(null)}
          onManual={() => navigate('profile')}
          onRefresh={() => {
            setSelected(null);
            started.current = Date.now();
            setPaused(false);
            resource.refresh();
          }}
          onApplied={() => {
            setSelected(null);
            notify('Reviewed sections imported. Confirm the updated profile before matching.');
            navigate('profile');
          }}
        />
      )}
    </>
  );
}
