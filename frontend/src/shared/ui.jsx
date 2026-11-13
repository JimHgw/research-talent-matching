import React, { useEffect, useRef } from 'react';
import { useLanguage } from './i18n.jsx';
import { labels } from './profile-labels.js';

const fieldLabels = {
  ...labels,
  email: 'Email address',
  password: 'Password',
  institution: 'Institution',
  qualification: 'Qualification',
  discipline: 'Discipline',
  startYear: 'Start year',
  endYear: 'End year',
  name: 'Course name',
  code: 'Course code',
  description: 'Description',
  title: 'Opportunity title',
  organisation: 'Organisation',
  type: 'Type',
  url: 'Link (optional)',
  evidenceText: 'Supporting evidence',
  label: 'Personal interest label',
  university: 'Organisation',
  researchArea: 'Research area',
  q: 'Search',
  skill: 'Skills',
  opportunityType: 'Opportunity type',
  deadlineAt: 'Deadline',
  deadlineFrom: 'Deadline from',
  deadlineTo: 'Deadline before',
  skillTagId: 'Skills',
  interestTagId: 'Research interests',
};

const paths = {
  grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  user: 'M20 21v-2a7 7 0 0 0-14 0v2 M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  file: 'M14 2H5v20h14V7z M14 2v6h5 M8 13h8 M8 17h6',
  compass: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M16 8l-3 5-5 3 3-5z',
  shield: 'M12 2l8 4v6c0 5-8 10-8 10S4 17 4 12V6z M8 12l3 3 5-6',
  briefcase: 'M3 7h18v14H3z M8 7V3h8v4 M3 12c6 3 12 3 18 0 M10 12h4v4h-4z',
  arrow: 'M5 12h14 M14 7l5 5-5 5',
  plus: 'M12 5v14 M5 12h14',
  check: 'M5 12l4 4L19 6',
  close: 'M6 6l12 12 M18 6 6 18',
  logout: 'M9 3H4v18h5 M10 12h11 M16 7l5 5-5 5',
  upload: 'M12 16V3 M7 8l5-5 5 5 M4 16v5h16v-5',
  search: 'M16 16l5 5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  spark: 'M12 2l3 7 7 3-7 3-3 7-3-7-7-3 7-3z',
  info: 'M12 11v6 M12 7h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  chevron: 'M9 5l7 7-7 7',
  menu: 'M4 6h16 M4 12h16 M4 18h16',
};
export function Icon({ name, size = 20 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.grid} />
    </svg>
  );
}
export function Brand() {
  return (
    <span className="brand" dir="ltr">
      <span className="brand-mark">
        b<span>·</span>
      </span>
      <span>
        banana<span className="brand-dot">.</span>
      </span>
    </span>
  );
}
export function Badge({ status, children }) {
  const { t } = useLanguage();
  return (
    <span className={`badge ${String(status || '').toLowerCase()}`}>
      {children || t(String(status).replaceAll('_', ' '))}
    </span>
  );
}
export function Button({ children, variant = 'primary', className = '', ...props }) {
  return (
    <button type="button" className={`button ${variant} ${className}`} {...props}>
      {children}
    </button>
  );
}
export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function ErrorNotice({ error, retry }) {
  const { t, errorMessage } = useLanguage();
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      <Icon name="info" />
      <div>
        <strong>{errorMessage(error)}</strong>
        {error.fields?.map((f, i) => (
          <p key={i}>
            {t(
              fieldLabels[
                f.field
                  .replace(/\[\d+\]/g, '')
                  .split('.')
                  .at(-1)
              ] || 'Submitted field'
            )}
            : {t(f.message)}
          </p>
        ))}
        {retry && (
          <Button variant="text" onClick={retry}>
            {t('Reload latest data')}
          </Button>
        )}
      </div>
    </div>
  );
}
export function Notice({ children, tone = 'info' }) {
  return (
    <div className={`notice ${tone}`}>
      <Icon name={tone === 'success' ? 'check' : 'info'} />
      <div>{children}</div>
    </div>
  );
}
export function Loading() {
  const { t } = useLanguage();
  return (
    <div className="loading" role="status">
      <span className="spinner" />
      {t('Loading your workspace…')}
    </div>
  );
}
export function Empty({ icon = 'compass', title, children, action }) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Icon name={icon} size={28} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Pager({ data, onPage }) {
  const { t } = useLanguage();
  if (!data || data.total <= data.pageSize) return null;
  return (
    <div className="pager">
      <Button variant="secondary" disabled={data.page === 1} onClick={() => onPage(data.page - 1)}>
        {t('Previous')}
      </Button>
      <span>
        {t('Page {page} of {pages}', {
          page: data.page,
          pages: Math.ceil(data.total / data.pageSize),
        })}
      </span>
      <Button
        variant="secondary"
        disabled={data.page * data.pageSize >= data.total}
        onClick={() => onPage(data.page + 1)}
      >
        {t('Next')}
      </Button>
    </div>
  );
}
export function Modal({ title, children, onClose }) {
  const { t } = useLanguage();
  const ref = useRef();
  useEffect(() => {
    const dialog = ref.current;
    const owner = dialog.ownerDocument;
    const trigger = owner.activeElement;
    dialog.showModal();
    return () => {
      const active = owner.activeElement;
      if (dialog.open) dialog.close?.();
      if (trigger?.isConnected && (active === owner.body || dialog.contains(active))) {
        trigger.focus();
      }
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <header>
        <h2>{title}</h2>
        <Button variant="icon" aria-label={t('Close dialog')} onClick={onClose}>
          <Icon name="close" />
        </Button>
      </header>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
