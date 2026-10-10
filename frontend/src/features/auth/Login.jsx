import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { Brand, Button, ErrorNotice, Field, Icon } from '../../shared/ui.jsx';
import PasswordReset from './PasswordReset.jsx';
import Register from './Register.jsx';

export default function Login({ onLogin }) {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetComplete, setResetComplete] = useState(false);
  const [registering, setRegistering] = useState(() => window.location.pathname === '/register');
  useEffect(() => {
    function followHistory() {
      setRegistering(window.location.pathname === '/register');
      setResetting(false);
      setResetComplete(false);
      setPassword('');
      setError(null);
    }
    window.addEventListener('popstate', followHistory);
    return () => window.removeEventListener('popstate', followHistory);
  }, []);

  function showRegistration(next) {
    window.history.pushState(null, '', next ? '/register' : '/');
    setRegistering(next);
    setResetting(false);
    setResetComplete(false);
    setPassword('');
    setError(null);
  }

  async function login(e) {
    e?.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const session = await api.login(identifier, password);
      onLogin(session.user);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <Brand />
        <span className="eyebrow light">RESEARCH, CONNECTED</span>
        <h1>
          Great research
          <br />
          starts with the
          <br />
          <em>right connection.</em>
        </h1>
        <p>
          Bring your experience to new opportunities.
          <br />
          See the evidence behind every match.
        </p>
        <div className="orbital-art" aria-hidden="true">
          <span className="orbit o1" />
          <span className="orbit o2" />
          <span className="art-label al1">
            <Icon name="user" />
            Your potential
          </span>
          <span className="art-label al2">
            <Icon name="spark" />
            Shared discovery
          </span>
          <span className="art-core">
            <Icon name="compass" size={44} />
          </span>
          <i className="star s1" />
          <i className="star s2" />
          <i className="star s3" />
        </div>
        <footer>
          H18ABANANA <span>STEM & BUSINESS · SPRINT 1</span>
        </footer>
      </section>
      <section className="login-form">
        <div className="login-card">
          <div className="eyebrow">YOUR RESEARCH WORKSPACE</div>
          {registering ? (
            <Register
              initialEmail={identifier.includes('@') ? identifier : ''}
              onBack={() => showRegistration(false)}
              onRegister={(user) => {
                window.history.replaceState(null, '', '/');
                onLogin(user);
              }}
            />
          ) : resetting ? (
            <PasswordReset
              initialIdentifier={identifier}
              onBack={() => setResetting(false)}
              onComplete={(account) => {
                setIdentifier(account);
                setPassword('');
                setError(null);
                setResetting(false);
                setResetComplete(true);
              }}
            />
          ) : (
            <>
              <h2>Welcome to Banana.</h2>
              <p className="muted">Sign in to find opportunities or discover research talent.</p>
              {resetComplete && (
                <p className="notice success" role="status">
                  Password updated. Sign in with your new password.
                </p>
              )}
              <ErrorNotice error={error} />
              <form onSubmit={login}>
                <Field label="Email address or account ID">
                  <input
                    type="text"
                    autoComplete="username"
                    placeholder="you@university.edu.au or user_…"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    maxLength={254}
                    required
                  />
                </Field>
                <Field label="Password">
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="Enter your password"
                  />
                </Field>
                <Button type="submit" disabled={busy} className="full">
                  {busy ? 'Signing in…' : 'Sign in'}
                  <Icon name="arrow" size={17} />
                </Button>
              </form>
              <Button
                variant="secondary"
                className="full"
                disabled={busy}
                onClick={() => showRegistration(true)}
              >
                Register
              </Button>
              <Button
                variant="text"
                className="full"
                disabled={busy}
                onClick={() => {
                  setPassword('');
                  setError(null);
                  setResetComplete(false);
                  setResetting(true);
                }}
              >
                Reset password
              </Button>
            </>
          )}
          <div className="login-foot">
            <Icon name="shield" size={17} />
            Your profile starts private. You choose what to share.
          </div>
        </div>
      </section>
    </main>
  );
}
