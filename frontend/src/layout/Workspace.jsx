import React, { useState } from 'react';
import { Button, ErrorNotice, Modal } from '../shared/ui.jsx';
import { WorkspaceSidebar, WorkspaceHeader, WorkspaceToast } from './WorkspaceChrome.jsx';
import { useMobileMenu, useToast } from './hooks.js';
import { useWorkspaceNavigation } from './useWorkspaceNavigation.js';
import AccountDetails from './AccountDetails.jsx';
import { useLanguage } from '../shared/i18n.jsx';

export default function Workspace({ user, onLogout, configuration }) {
  const { t } = useLanguage();
  const [accountOpen, setAccountOpen] = useState(false);
  const team = user.role === 'RESEARCH_TEAM';
  const definition = configuration[user.role];
  const nav = definition.navigation;
  const menu = useMobileMenu();
  const { toast, setToast } = useToast();
  const navigation = useWorkspaceNavigation(definition, onLogout, menu.close);
  const {
    page,
    pageContext,
    navigate,
    onDirty,
    onPending,
    pending,
    cancel,
    discard,
    busy,
    logoutError,
  } = navigation;
  const Page = definition.pages[page];
  const chrome = {
    user,
    team,
    nav,
    page,
    navigate,
    mobileMenu: menu.open,
    setMobileMenu: menu.setOpen,
  };
  return (
    <div className="workspace">
      <WorkspaceSidebar {...chrome} />
      <div className="workspace-body" inert={menu.open}>
        <WorkspaceHeader {...chrome} onAccount={() => setAccountOpen(true)} />
        <main className="main-content" id="main">
          <div className="page-heading">
            <div className="eyebrow">{t(team ? 'RESEARCH TEAM' : 'RESEARCH TALENT')}</div>
            <h1>
              {page === 'overview'
                ? t('Good to see you, {name}.', { name: user.displayName.split(' ')[0] })
                : t(nav.find((n) => n[0] === page)?.[2] || '')}
            </h1>
            {page === 'overview' && (
              <p>{t('Make your next research connection a meaningful one.')}</p>
            )}
          </div>
          <ErrorNotice error={logoutError} />
          <Page
            key={page}
            notify={setToast}
            navigate={navigate}
            onDirty={onDirty}
            onPending={onPending}
            {...definition.pageProps?.[page]}
            {...pageContext}
            user={user}
            overview={page === 'overview'}
          />
          <footer className="page-footer">
            <span>{t('Banana · Research, connected.')}</span>
            <span>{t('Sprint 1 prototype')}</span>
          </footer>
        </main>
      </div>
      <WorkspaceToast toast={toast} setToast={setToast} />
      {accountOpen && (
        <AccountDetails
          user={user}
          onClose={() => setAccountOpen(false)}
          onSwitch={() => {
            setAccountOpen(false);
            navigate('logout');
          }}
        />
      )}
      {pending && (
        <Modal title={t(busy ? 'Please wait' : 'Leave without saving?')} onClose={cancel}>
          <p>
            {t(
              busy
                ? 'Wait for the current operation to finish before leaving this page.'
                : 'Your unsaved edits will be discarded. Save your changes first if you want to keep them.'
            )}
          </p>
          <div className="actions">
            <Button variant="secondary" onClick={cancel}>
              {t('Keep editing')}
            </Button>
            <Button disabled={busy} onClick={discard}>
              {t('Discard changes')}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
