import React, { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client.js';
import { Button, ErrorNotice, Field } from '../../shared/ui.jsx';
import PasswordInput from '../../shared/PasswordInput.jsx';
import { useLanguage } from '../../shared/i18n.jsx';

const passwordHint =
  'At least 8 characters, including an uppercase letter, a lowercase letter and a digit.';

export default function Register({ initialEmail = '', onBack, onRegister }) {
  const { t } = useLanguage();
  const mounted = useRef(false);
  const [email, setEmail] = useState(initialEmail);
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState('TALENT');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [resendAt, setResendAt] = useState(0);
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const tick = () => setRemaining(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [resendAt]);

  async function sendCode() {
    const address = email.trim().toLowerCase();
    const response = await api.requestRegistrationCode(address);
    if (!mounted.current) return;
    setEmail(address);
    setResendAt(Date.now() + response.resendAfterSeconds * 1000);
    setCode('');
    setSent(true);
  }

  async function run(operation) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError(null);
    try {
      await operation();
    } catch (failure) {
      if (mounted.current) setError(failure);
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (!sent) {
      if (remaining > 0) return;
      await run(sendCode);
      return;
    }
    await run(async () => {
      if (!/^[0-9]{6}$/.test(code)) throw new Error('Enter the six-digit code from your email.');
      if (!displayName.trim()) throw new Error("Enter your name or your research team's name.");
      if (
        password.length < 8 ||
        password.length > 200 ||
        !/[A-Z]/.test(password) ||
        !/[a-z]/.test(password) ||
        !/[0-9]/.test(password)
      ) {
        throw new Error(passwordHint);
      }
      if (password !== confirmPassword) throw new Error('The passwords must match.');
      const session = await api.register({
        email: email.trim().toLowerCase(),
        code,
        password,
        displayName: displayName.trim(),
        role,
      });
      if (mounted.current) onRegister(session.user);
    });
  }

  function changeEmail() {
    setSent(false);
    setCode('');
    setPassword('');
    setConfirmPassword('');
    setError(null);
  }

  return (
    <>
      <h2>{t('Create your Banana account.')}</h2>
      <p className="muted">
        {t('Join as research talent or a research team. Start by verifying your email.')}
      </p>
      <ErrorNotice error={error} />
      <form onSubmit={submit}>
        <fieldset className="registration-fields" disabled={busy}>
          <Field label={t('Email address')}>
            <input
              type="email"
              dir="ltr"
              autoComplete="email"
              placeholder="you@university.edu.au"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              readOnly={sent}
              maxLength={254}
              required
            />
          </Field>
          {sent && (
            <>
              <p className="muted" role="status">
                {t(
                  'A six-digit code has been sent to your email. It expires in 10 minutes. Use the most recent code to create your account.'
                )}
              </p>
              <Field label={t('Verification code')}>
                <input
                  inputMode="numeric"
                  dir="ltr"
                  autoComplete="one-time-code"
                  placeholder="012345"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  pattern="[0-9]{6}"
                  minLength={6}
                  maxLength={6}
                  required
                />
              </Field>
              <div className="registration-code-actions">
                <Button
                  variant="text"
                  disabled={remaining > 0}
                  onClick={() => remaining === 0 && run(sendCode)}
                >
                  {remaining > 0
                    ? t('Resend in {seconds}s', { seconds: remaining })
                    : t('Resend code')}
                </Button>
                <Button variant="text" onClick={changeEmail}>
                  {t('Change email')}
                </Button>
              </div>
              <Field label={t('Account type')}>
                <select value={role} onChange={(event) => setRole(event.target.value)}>
                  <option value="TALENT">{t('Research talent')}</option>
                  <option value="RESEARCH_TEAM">{t('Research team')}</option>
                </select>
              </Field>
              <Field label={t('Display name')} hint={t("Your name or your research team's name.")}>
                <input
                  autoComplete="nickname"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  maxLength={100}
                  required
                />
              </Field>
              <Field label={t('Password')} hint={t(passwordHint)}>
                <PasswordInput
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  maxLength={200}
                  required
                />
              </Field>
              <Field label={t('Confirm password')}>
                <PasswordInput
                  label={t('Confirm password')}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  maxLength={200}
                  required
                />
              </Field>
            </>
          )}
          <Button type="submit" className="full" disabled={!sent && remaining > 0}>
            {busy
              ? t('Please wait…')
              : sent
                ? t('Create account')
                : remaining > 0
                  ? t('Send code in {seconds}s', { seconds: remaining })
                  : t('Send verification code')}
          </Button>
        </fieldset>
      </form>
      <Button variant="text" className="full" disabled={busy} onClick={onBack}>
        {t('Back to sign in')}
      </Button>
    </>
  );
}
