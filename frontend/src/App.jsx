import React from 'react';
import { api } from './api/client.js';
import { Brand, Button, ErrorNotice, Loading } from './shared/ui.jsx';
import { LanguageProvider, useLanguage } from './shared/i18n.jsx';
import LanguageSelect from './shared/LanguageSelect.jsx';
import { useMutation } from './shared/useMutation.js';
import { useAccountSession } from './features/auth/useAccountSession.js';
import Login from './features/auth/Login.jsx';
import Workspace from './layout/Workspace.jsx';
import { workspaceConfiguration } from './app/workspace-config.jsx';

export default function App({ configuration = workspaceConfiguration }) {
  return (
    <LanguageProvider>
      <AccountSession configuration={configuration} />
    </LanguageProvider>
  );
}

function AccountSession({ configuration }) {
  const { t } = useLanguage();
  const session = useAccountSession();
  const logout = useMutation();
  const { user } = session;
  if (session.loading)
    return (
      <main className="app-loading">
        <Brand />
        <Loading />
      </main>
    );
  if (session.error)
    return (
      <main className="fatal">
        <Brand />
        <LanguageSelect />
        <h1>{t('We could not reach your workspace.')}</h1>
        <ErrorNotice error={session.error} retry={session.refresh} />
        <p>{t('The service is currently unavailable. Please try again shortly.')}</p>
      </main>
    );
  // Roles are supplied by the authenticated session, never by a local selector.
  if (user && !Object.hasOwn(configuration, user.role))
    return (
      <main className="fatal">
        <Brand />
        <LanguageSelect />
        <h1>{t('Your account cannot open this workspace.')}</h1>
        <p>{t('Sign out and use an account with an authorised role.')}</p>
        <ErrorNotice error={logout.error} />
        <Button
          disabled={logout.busy}
          onClick={() => logout.run(api.logout, () => session.refresh({ clearUser: true }))}
        >
          {t('Sign out')}
        </Button>
      </main>
    );
  return user ? (
    <Workspace
      configuration={configuration}
      key={`${user.id}:${user.role}`}
      user={user}
      onLogout={() => session.refresh({ clearUser: true })}
    />
  ) : (
    <Login onLogin={session.accept} />
  );
}
