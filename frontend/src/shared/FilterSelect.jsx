import React, { useEffect, useId, useRef, useState } from 'react';
import { useLanguage } from './i18n.jsx';

export default function FilterSelect({ label, choices, value = [], onChange, multiple = true }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef(null);
  const trigger = useRef(null);
  const keyboardOpen = useRef(false);
  const selectedIds = multiple ? value : value.slice(0, 1);
  const selected = choices.filter((choice) => selectedIds.includes(choice.id));

  useEffect(() => {
    if (!open) return;
    function outside(event) {
      if (!root.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener('pointerdown', outside);
    if (keyboardOpen.current) {
      (
        root.current.querySelector('[aria-selected="true"]') ||
        root.current.querySelector('[role="option"]')
      )?.focus();
      keyboardOpen.current = false;
    }
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);

  function keyDown(event) {
    if (event.key === 'Escape' && open) {
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      trigger.current.focus();
    }
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    if (!open) {
      keyboardOpen.current = true;
      setOpen(true);
      return;
    }
    const options = [...root.current.querySelectorAll('[role="option"]')];
    const current = options.indexOf(document.activeElement);
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? options.length - 1
          : current < 0
            ? event.key === 'ArrowUp'
              ? options.length - 1
              : 0
            : (current + (event.key === 'ArrowUp' ? -1 : 1) + options.length) % options.length;
    options[next]?.focus();
  }

  return (
    <div
      className="field filter-select"
      ref={root}
      onKeyDown={keyDown}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <span id={`${id}-label`}>{t(label)}</span>
      <button
        type="button"
        className="filter-select-trigger"
        ref={trigger}
        aria-label={t(label)}
        aria-describedby={`${id}-value`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${id}-options` : undefined}
        onClick={() => setOpen((previous) => !previous)}
      >
        <span id={`${id}-value`} className="filter-select-values">
          {selected.length ? (
            selected.map((choice) => (
              <span className="filter-select-value" key={choice.id}>
                {t(choice.label)}
              </span>
            ))
          ) : (
            <span className="filter-select-placeholder">
              {t(multiple ? 'Select options' : 'Not specified')}
            </span>
          )}
        </span>
        <svg
          className="filter-select-arrow"
          width="14"
          height="14"
          viewBox="0 0 14 14"
          aria-hidden="true"
        >
          <path d="m3 5 4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>
      {open && (
        <div
          id={`${id}-options`}
          className="filter-select-options"
          role="listbox"
          aria-labelledby={`${id}-label`}
          aria-multiselectable={multiple}
        >
          {choices.map((choice) => (
            <button
              type="button"
              role="option"
              key={choice.id}
              tabIndex={-1}
              aria-selected={selectedIds.includes(choice.id)}
              onClick={() => {
                onChange(
                  !multiple
                    ? [choice.id]
                    : value.includes(choice.id)
                      ? value.filter((item) => item !== choice.id)
                      : [...value, choice.id]
                );
                setOpen(false);
                trigger.current.focus();
              }}
            >
              <span className="filter-select-check" aria-hidden="true">
                {selectedIds.includes(choice.id) ? '✓' : ''}
              </span>
              <span>{t(choice.label)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
