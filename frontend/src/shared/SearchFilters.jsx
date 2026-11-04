import React, { useState } from 'react';
import { useLanguage } from './i18n.jsx';
import { Button, Field, ErrorNotice } from './ui.jsx';
import { dateTimeZone, go8Universities, opportunityTypes } from './search.js';
import FilterSelect from './FilterSelect.jsx';

export default function SearchFilters({ onApply, talent = false, initialFilters = {} }) {
  const { t } = useLanguage();
  const [draft, setDraft] = useState(initialFilters);
  const [applied, setApplied] = useState(initialFilters);
  const [error, setError] = useState(null);
  const set = (key, value) => setDraft((previous) => ({ ...previous, [key]: value }));
  function selection(key, label, choices, multiple = true) {
    const value = draft[key];
    return (
      <FilterSelect
        label={label}
        choices={choices}
        multiple={multiple}
        value={Array.isArray(value) ? value : value ? [value] : []}
        onChange={(next) => set(key, multiple ? next : next[0] || '')}
      />
    );
  }
  function apply(event) {
    event.preventDefault();
    setError(null);
    if (
      draft.deadlineFrom &&
      draft.deadlineTo &&
      new Date(draft.deadlineFrom) >= new Date(draft.deadlineTo)
    ) {
      setError({
        code: 'VALIDATION_ERROR',
        message: t('The upper deadline bound must be later than the lower bound.'),
      });
      return;
    }
    const filters = {};
    for (const [key, value] of Object.entries(draft)) {
      if (Array.isArray(value) ? !value.length : !value.trim()) continue;
      filters[key] =
        talent && key === 'university'
          ? Array.isArray(value)
            ? value[0]
            : value
          : key.startsWith('deadline')
            ? new Date(value).toISOString()
            : value;
    }
    setApplied(structuredClone(draft));
    onApply(filters);
  }
  return (
    <form
      className="panel search-filters"
      aria-label={t(talent ? 'Talent filters' : 'Opportunity filters')}
      onSubmit={apply}
    >
      <ErrorNotice error={error} />
      {Object.entries(applied).some(([, value]) =>
        Array.isArray(value) ? value.length : value
      ) && (
        <p role="status">
          {t('Active filters')}: {Object.values(applied).flat().filter(Boolean).join(' · ')}
        </p>
      )}
      <div className="search-filter-grid">
        <Field label={t('Search')}>
          <input
            type="search"
            maxLength={200}
            value={draft.q || ''}
            onChange={(e) => set('q', e.target.value)}
          />
        </Field>
        {talent ? (
          <>
            <Field label={t('Skills')}>
              <input
                type="search"
                maxLength={200}
                value={draft.skill || ''}
                onChange={(e) => set('skill', e.target.value)}
              />
            </Field>
            {selection('university', 'University', go8Universities, false)}
          </>
        ) : (
          <>
            {[
              ['university', 'Organisation'],
              ['discipline', 'Discipline'],
              ['researchArea', 'Research area'],
            ].map(([key, label]) => (
              <Field key={key} label={t(label)}>
                <input
                  maxLength={key === 'researchArea' ? 300 : 200}
                  value={draft[key] || ''}
                  onChange={(e) => set(key, e.target.value)}
                />
              </Field>
            ))}
            {selection(
              'disciplineGroup',
              'Discipline group',
              ['STEM', 'BUSINESS'].map((id) => ({ id, label: id }))
            )}
            {selection(
              'opportunityType',
              'Opportunity type',
              opportunityTypes.map((id) => ({ id, label: id }))
            )}
            {[
              ['deadlineFrom', 'Deadline from'],
              ['deadlineTo', 'Deadline before'],
            ].map(([key, label]) => (
              <Field key={key} label={t(label)}>
                <input
                  type="datetime-local"
                  value={draft[key] || ''}
                  onChange={(e) => set(key, e.target.value)}
                />
              </Field>
            ))}
          </>
        )}
      </div>
      {!talent && (
        <p className="help">
          {t('Dates use {zone}; the upper bound is exclusive.', { zone: dateTimeZone() })}
        </p>
      )}
      <div className="actions">
        <Button type="submit">{t('Apply filters')}</Button>
        <Button
          variant="secondary"
          onClick={() => {
            setDraft({});
            setApplied({});
            setError(null);
            onApply({});
          }}
        >
          {t('Clear filters')}
        </Button>
      </div>
    </form>
  );
}
