import React, { useEffect, useState } from 'react';
import { api } from '../../api/client.js';
import { Brand, Button, ErrorNotice, Field, Icon } from '../../shared/ui.jsx';
import PasswordReset from './PasswordReset.jsx';
import Register from './Register.jsx';
import LanguageSelect from '../../shared/LanguageSelect.jsx';
import PasswordInput from '../../shared/PasswordInput.jsx';
import { useLanguage } from '../../shared/i18n.jsx';
import { useMutation } from '../../shared/useMutation.js';

export default function Login({ onLogin }) {
  const { t } = useLanguage();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const { error, clearError, busy, run } = useMutation();
  const [resetting, setResetting] = useState(false);
  const [resetComplete, setResetComplete] = useState(false);
  const [registering, setRegistering] = useState(() => window.location.pathname === '/register');
  useEffect(() => {
    function followHistory() {
      setRegistering(window.location.pathname === '/register');
      setResetting(false);
      setResetComplete(false);
      setPassword('');
      clearError();
    }
    window.addEventListener('popstate', followHistory);
    return () => window.removeEventListener('popstate', followHistory);
  }, [clearError]);

  function showRegistration(next) {
    window.history.pushState(null, '', next ? '/register' : '/');
    setRegistering(next);
    setResetting(false);
    setResetComplete(false);
    setPassword('');
    clearError();
  }

  async function login(e) {
    e?.preventDefault();
    clearError();
    await run(
      () => api.login(identifier.trim(), password),
      (session) => onLogin(session.user)
    );
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <Brand />
        <span className="eyebrow light">{t('RESEARCH, CONNECTED')}</span>
        <h1>
          {t('Great research')}
          <br />
          {t('starts with the')}
          <br />
          <em>{t('right connection.')}</em>
        </h1>
        <p>
          {t('Bring your experience to new opportunities.')}
          <br />
          {t('See the evidence behind every match.')}
        </p>
        <div className="orbital-art" aria-hidden="true">
          <span className="orbit o1" />
          <span className="orbit o2" />
          <span className="art-label al1">
            <Icon name="user" />
            {t('Your potential')}
          </span>
          <span className="art-label al2">
            <Icon name="spark" />
            {t('Shared discovery')}
          </span>
          <span className="art-core">
            <Icon name="compass" size={44} />
          </span>
          <i className="star s1" />
          <i className="star s2" />
          <i className="star s3" />
        </div>
        <footer>
          H18ABANANA <span>{t('STEM & BUSINESS · SPRINT 1')}</span>
        </footer>
      </section>
      <section className="login-form">
        <div className="login-card">
          <LanguageSelect />
          <div className="eyebrow">{t('YOUR RESEARCH WORKSPACE')}</div>
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
                clearError();
                setResetting(false);
                setResetComplete(true);
              }}
            />
          ) : (
            <>
              <h2>{t('Welcome to Banana.')}</h2>
              <p className="muted">
                {t('Sign in to find opportunities or discover research talent.')}
              </p>
              {resetComplete && (
                <p className="notice success" role="status">
                  {t('Password updated. Sign in with your new password.')}
                </p>
              )}
              <ErrorNotice error={error} />
              <form onSubmit={login}>
                <fieldset className="login-fields" disabled={busy}>
                  <Field label={t('Email address or account ID')}>
                    <input
                      type="text"
                      dir="ltr"
                      autoComplete="username"
                      placeholder={t('you@university.edu.au or user_…')}
                      value={identifier}
                      onChange={(e) => setIdentifier(e.target.value)}
                      maxLength={254}
                      required
                    />
                  </Field>
                  <Field label={t('Password')}>
                    <PasswordInput
                      autoComplete="current-password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      placeholder={t('Enter your password')}
                    />
                  </Field>
                  <Button type="submit" disabled={busy} className="full">
                    {t(busy ? 'Signing in…' : 'Sign in')}
                    <Icon name="arrow" size={17} />
                  </Button>
                </fieldset>
              </form>
              <Button
                variant="secondary"
                className="full"
                disabled={busy}
                onClick={() => showRegistration(true)}
              >
                {t('Register')}
              </Button>
              <Button
                variant="text"
                className="full"
                disabled={busy}
                onClick={() => {
                  setPassword('');
                  clearError();
                  setResetComplete(false);
                  setResetting(true);
                }}
              >
                {t('Reset password')}
              </Button>
            </>
          )}
          <div className="login-foot">
            <Icon name="shield" size={17} />
            {t('Your profile starts private. You choose what to share.')}
          </div>
        </div>
      </section>
    </main>
  );
}
