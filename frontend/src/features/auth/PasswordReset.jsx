import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { Button, ErrorNotice, Field } from '../../shared/ui.jsx';
import PasswordInput from '../../shared/PasswordInput.jsx';
import { useLanguage } from '../../shared/i18n.jsx';

const passwordHint =
  'At least 8 characters, including an uppercase letter, a lowercase letter and a digit.';

export default function PasswordReset({ initialIdentifier, onBack, onComplete }) {
  const { t } = useLanguage();
  const [method, setMethod] = useState('PASSWORD');
  const [identifier, setIdentifier] = useState(initialIdentifier);
  const [email, setEmail] = useState(initialIdentifier.includes('@') ? initialIdentifier : '');
  const [stage, setStage] = useState('email');
  const [code, setCode] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [resendAt, setResendAt] = useState(0);
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    const tick = () => setRemaining(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [resendAt]);

  function selectMethod(next) {
    setMethod(next);
    setStage('email');
    setCode('');
    setCurrentPassword('');
    setNewPassword('');
    setConfirmPassword('');
    setError(null);
  }

  async function sendCode() {
    const response = await api.requestPasswordResetCode(email.trim());
    setResendAt(Date.now() + response.resendAfterSeconds * 1000);
    setCode('');
    setStage('code');
  }

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      if (method === 'EMAIL_CODE' && stage === 'email') {
        await sendCode();
      } else if (method === 'EMAIL_CODE' && stage === 'code') {
        await api.verifyPasswordResetCode(email.trim(), code);
        setStage('new');
      } else {
        if (
          newPassword.length < 8 ||
          newPassword.length > 200 ||
          !/[A-Z]/.test(newPassword) ||
          !/[a-z]/.test(newPassword) ||
          !/[0-9]/.test(newPassword)
        ) {
          throw new Error(passwordHint);
        }
        if (newPassword !== confirmPassword) throw new Error('The new passwords must match.');
        if (method === 'PASSWORD' && newPassword === currentPassword) {
          throw new Error('The new password must be different from the current password.');
        }
        const account =
          method === 'PASSWORD'
            ? { identifier: identifier.trim(), currentPassword }
            : { email: email.trim() };
        await api.resetPassword({ method, ...account, newPassword, confirmPassword });
        onComplete(method === 'PASSWORD' ? identifier.trim() : email.trim());
      }
    } catch (failure) {
      setError(failure);
      if (failure.code === 'VERIFICATION_CODE_INVALID' && stage === 'new') {
        setStage('email');
        setNewPassword('');
        setConfirmPassword('');
      }
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    if (busy || remaining > 0) return;
    setBusy(true);
    setError(null);
    try {
      await sendCode();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  const choosingPassword = method === 'PASSWORD' || stage === 'new';
  return (
    <>
      <h2>{t('Reset your password.')}</h2>
      <p className="muted">{t('Choose how to verify your account.')}</p>
      <div className="reset-methods" role="group" aria-label={t('Password reset method')}>
        <Button
          variant="secondary"
          aria-pressed={method === 'PASSWORD'}
          disabled={busy}
          onClick={() => selectMethod('PASSWORD')}
        >
          {t('I remember my password')}
        </Button>
        <Button
          variant="secondary"
          aria-pressed={method === 'EMAIL_CODE'}
          disabled={busy}
          onClick={() => selectMethod('EMAIL_CODE')}
        >
          {t('Use an email code')}
        </Button>
      </div>
      <ErrorNotice error={error} />
      <form onSubmit={submit}>
        <fieldset className="reset-fields" disabled={busy}>
          {method === 'PASSWORD' ? (
            <>
              <Field label={t('Email address or account ID')}>
                <input
                  dir="ltr"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  autoComplete="username"
                  required
                  maxLength={254}
                />
              </Field>
              <Field label={t('Current password')}>
                <PasswordInput
                  label="Current password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  required
                  maxLength={200}
                />
              </Field>
            </>
          ) : (
            <>
              <Field label={t('Email address')}>
                <input
                  type="email"
                  dir="ltr"
                  autoComplete="email"
                  value={email}
                  readOnly={stage !== 'email'}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  maxLength={254}
                />
              </Field>
              {stage === 'code' && (
                <>
                  <p className="muted" role="status">
                    {t(
                      'If this email has an account, a six-digit code has been sent. It expires in 10 minutes.'
                    )}
                  </p>
                  <Field label={t('Verification code')}>
                    <input
                      inputMode="numeric"
                      dir="ltr"
                      autoComplete="one-time-code"
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                      pattern="[0-9]{6}"
                      minLength={6}
                      maxLength={6}
                      required
                      placeholder="012345"
                    />
                  </Field>
                  <Button variant="text" disabled={remaining > 0} onClick={resend}>
                    {remaining > 0
                      ? t('Resend in {seconds}s', { seconds: remaining })
                      : t('Resend code')}
                  </Button>
                </>
              )}
              {stage === 'new' && (
                <p role="status" className="muted">
                  {t('Email verified. Choose your new password.')}
                </p>
              )}
            </>
          )}
          {choosingPassword && (
            <>
              <Field label={t('New password')} hint={t(passwordHint)}>
                <PasswordInput
                  label="New password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  required
                  maxLength={200}
                />
              </Field>
              <Field label={t('Confirm new password')}>
                <PasswordInput
                  label="Confirm new password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                  maxLength={200}
                />
              </Field>
            </>
          )}
          <Button type="submit" className="full">
            {busy
              ? t('Please wait…')
              : choosingPassword
                ? t('Update password')
                : stage === 'email'
                  ? t('Send code')
                  : t('Verify email')}
          </Button>
        </fieldset>
      </form>
      <Button variant="text" className="full" disabled={busy} onClick={onBack}>
        {t('Back to sign in')}
      </Button>
    </>
  );
}
