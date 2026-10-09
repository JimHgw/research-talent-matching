import React from 'react';
import { Button, ErrorNotice, Modal } from '../shared/ui.jsx';
import { WorkspaceSidebar, WorkspaceHeader, WorkspaceToast } from './WorkspaceChrome.jsx';
import { useMobileMenu, useToast } from './hooks.js';
import { useWorkspaceNavigation } from './useWorkspaceNavigation.js';

export default function Workspace({ user, onLogout, configuration }) {
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
        <WorkspaceHeader {...chrome} />
        <main className="main-content" id="main">
          <div className="page-heading">
            <div className="eyebrow">{team ? 'RESEARCH TEAM' : 'RESEARCH TALENT'}</div>
            <h1>
              {page === 'overview'
                ? `Good to see you, ${user.displayName.split(' ')[0]}.`
                : nav.find((n) => n[0] === page)?.[2]}
            </h1>
            {page === 'overview' && <p>Make your next research connection a meaningful one.</p>}
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
            <span>Banana · Research, connected.</span>
            <span>Sprint 1 prototype</span>
          </footer>
        </main>
      </div>
      <WorkspaceToast toast={toast} setToast={setToast} />
      {pending && (
        <Modal title={busy ? 'Please wait' : 'Leave without saving?'} onClose={cancel}>
          <p>
            {busy
              ? 'Wait for the current operation to finish before leaving this page.'
              : 'Your unsaved edits will be discarded. Save your changes first if you want to keep them.'}
          </p>
          <div className="actions">
            <Button variant="secondary" onClick={cancel}>
              Keep editing
            </Button>
            <Button disabled={busy} onClick={discard}>
              Discard changes
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
