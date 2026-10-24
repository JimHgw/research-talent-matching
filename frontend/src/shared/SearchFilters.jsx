import React, { useState } from 'react';
import { useLanguage } from './i18n.jsx';
import { Button, Field } from './ui.jsx';
import { dateTimeZone, opportunityTypes } from './search.js';

export default function SearchFilters({ onApply, talent = false, tags = [], initialFilters = {} }) {
  const { t } = useLanguage();
  const [draft, setDraft] = useState(initialFilters);
  const set = (key, value) => setDraft((previous) => ({ ...previous, [key]: value }));
  function multiple(key, label, choices) {
    return (
      <Field label={t(label)}>
        <select
          multiple
          value={draft[key] || []}
          onChange={(event) =>
            set(
              key,
              [...event.target.selectedOptions].map((option) => option.value)
            )
          }
        >
          {choices.map(({ id, label: text }) => (
            <option key={id} value={id}>
              {t(text)}
            </option>
          ))}
        </select>
      </Field>
    );
  }
  function apply(event) {
    event.preventDefault();
    const filters = {};
    for (const [key, value] of Object.entries(draft)) {
      if (Array.isArray(value) ? !value.length : !value.trim()) continue;
      filters[key] = key.startsWith('deadline') ? new Date(value).toISOString() : value;
    }
    onApply(filters);
  }
  return (
    <form
      className="panel search-filters"
      aria-label={t(talent ? 'Talent filters' : 'Opportunity filters')}
      onSubmit={apply}
    >
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
            {multiple(
              'skillTagId',
              'Skills',
              tags.filter((tag) => tag.kind === 'SKILL')
            )}
            {multiple(
              'interestTagId',
              'Research interests',
              tags.filter((tag) => tag.kind === 'INTEREST')
            )}
          </>
        ) : (
          <>
            {[
              ['university', 'University'],
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
            {multiple(
              'disciplineGroup',
              'Discipline group',
              ['STEM', 'BUSINESS'].map((id) => ({ id, label: id }))
            )}
            {multiple(
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
      <p className="help">
        {t('Choose multiple options with Ctrl or Command. Filters combine across fields.')}
      </p>
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
            onApply({});
          }}
        >
          {t('Clear filters')}
        </Button>
      </div>
    </form>
  );
}
