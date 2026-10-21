import React, { useEffect, useId, useState } from 'react';
import { useLanguage } from './i18n.jsx';

export default function PasswordInput({ label = 'Password', value, ...props }) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  const { t } = useLanguage();
  useEffect(() => {
    if (!value) setVisible(false);
  }, [value]);
  return (
    <div className="password-input">
      <input
        {...props}
        id={id}
        type={visible ? 'text' : 'password'}
        dir="ltr"
        value={value}
        aria-label={t(label)}
      />
      <button
        type="button"
        aria-label={t(visible ? 'Hide {label}' : 'Show {label}', { label: t(label).toLowerCase() })}
        aria-controls={id}
        aria-pressed={visible}
        disabled={props.disabled}
        onClick={() => setVisible((current) => !current)}
      >
        {t(visible ? 'Hide' : 'Show')}
      </button>
    </div>
  );
}
