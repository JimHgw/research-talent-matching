import React, { useEffect, useRef, useState } from 'react';
import { api } from '../../api/client.js';
import { Button, ErrorNotice, Field } from '../../shared/ui.jsx';

const passwordHint =
  'At least 8 characters, including an uppercase letter, a lowercase letter and a digit.';

export default function Register({ initialEmail = '', onBack, onRegister }) {
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
    const tick = () => setRemaining(Math.max(0, Math.ceil((resendAt - Date.now()) / 1000)));
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [resendAt]);

  async function sendCode() {
    const address = email.trim().toLowerCase();
    const response = await api.requestRegistrationCode(address);
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
      setError(failure);
    } finally {
      pending.current = false;
      setBusy(false);
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
      onRegister(session.user);
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
      <h2>Create your Banana account.</h2>
      <p className="muted">
        Join as research talent or a research team. Start by verifying your email.
      </p>
      <ErrorNotice error={error} />
      <form onSubmit={submit}>
        <fieldset className="registration-fields" disabled={busy}>
          <Field label="Email address">
            <input
              type="email"
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
                A six-digit code has been sent to your email. It expires in 10 minutes. Use the most
                recent code to create your account.
              </p>
              <Field label="Verification code">
                <input
                  inputMode="numeric"
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
                  {remaining > 0 ? `Resend in ${remaining}s` : 'Resend code'}
                </Button>
                <Button variant="text" onClick={changeEmail}>
                  Change email
                </Button>
              </div>
              <Field label="Account type">
                <select value={role} onChange={(event) => setRole(event.target.value)}>
                  <option value="TALENT">Research talent</option>
                  <option value="RESEARCH_TEAM">Research team</option>
                </select>
              </Field>
              <Field label="Display name" hint="Your name or your research team's name.">
                <input
                  autoComplete="nickname"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  maxLength={100}
                  required
                />
              </Field>
              <Field label="Password" hint={passwordHint}>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  maxLength={200}
                  required
                />
              </Field>
              <Field label="Confirm password">
                <input
                  type="password"
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
              ? 'Please wait…'
              : sent
                ? 'Create account'
                : remaining > 0
                  ? `Send code in ${remaining}s`
                  : 'Send verification code'}
          </Button>
        </fieldset>
      </form>
      <Button variant="text" className="full" disabled={busy} onClick={onBack}>
        Back to sign in
      </Button>
    </>
  );
}
