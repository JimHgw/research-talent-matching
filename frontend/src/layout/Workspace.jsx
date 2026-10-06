import React, { useEffect, useState } from 'react';
import { api } from '../api/client.js';
import { Brand, Button, ErrorNotice, Icon, Modal } from '../shared/ui.jsx';

export default function Workspace({ user, onLogout, configuration }) {
  const team = user.role === 'RESEARCH_TEAM';
  const definition = configuration[user.role];
  const nav = definition.navigation;

  const [page, setPage] = useState(definition.defaultPage);
  const [pageContext, setPageContext] = useState({});
  const [mobileMenu, setMobileMenu] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(null);
  const [toast, setToast] = useState('');
  const [logoutError, setLogoutError] = useState(null);
  useEffect(() => {
    if (!mobileMenu) return;
    const onKey = (event) => {
      if (event.key === 'Escape') setMobileMenu(false);
    };
    const onResize = () => {
      if (window.innerWidth > 760) setMobileMenu(false);
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', onResize);
    };
  }, [mobileMenu]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 5500);
    return () => clearTimeout(timer);
  }, [toast]);
  async function go(target, context = {}) {
    if (target === 'logout') {
      try {
        await api.logout();
        onLogout();
      } catch (e) {
        setLogoutError(e);
      }
      return;
    }
    if (!definition.pages[target]) return;
    setDirty(false);
    setPageContext(context);
    setPage(target);
    setMobileMenu(false);
    window.scrollTo({ top: 0 });
  }
  function navigate(target, context = {}) {
    if (dirty && target !== page) setPending({ target, context });
    else go(target, context);
  }
  const Page = definition.pages[page];
  const shared = {
    notify: setToast,
    navigate,
    onDirty: setDirty,
  };
  return (
    <div className="workspace">
      <aside id="workspace-navigation" className={`sidebar ${mobileMenu ? 'mobile-open' : ''}`}>
        <div className="sidebar-brand">
          <Brand />
          <Button
            variant="icon"
            className="mobile-only"
            aria-label="Close navigation"
            onClick={() => setMobileMenu(false)}
          >
            <Icon name="close" />
          </Button>
        </div>
        <div className="workspace-selector">
          <span className="workspace-avatar">
            <Icon name={team ? 'briefcase' : 'user'} size={18} />
          </span>
          <div>
            <strong>{team ? 'Research team' : 'Talent workspace'}</strong>
            <small>University research</small>
          </div>
        </div>
        <span className="nav-caption">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {nav.map(([key, icon, label]) => (
            <button
              key={key}
              className={page === key ? 'active' : ''}
              aria-current={page === key ? 'page' : undefined}
              onClick={() => navigate(key)}
            >
              <Icon name={icon} />
              <span>{label}</span>
              {page === key && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Icon name="spark" />
            <strong>Make discovery meaningful.</strong>
            <p>
              Clear evidence.
              <br />
              Better connections.
            </p>
          </div>
          <div className="sidebar-user">
            <span className="avatar">
              {user.displayName
                .split(' ')
                .map((n) => n[0])
                .join('')
                .slice(0, 2)}
            </span>
            <div>
              <strong>{user.displayName}</strong>
              <small>{team ? 'Research team' : 'Research talent'}</small>
            </div>
            <Button variant="icon" aria-label="Sign out" onClick={() => navigate('logout')}>
              <Icon name="logout" size={18} />
            </Button>
          </div>
        </div>
      </aside>
      {mobileMenu && (
        <button
          className="menu-backdrop"
          aria-label="Close navigation"
          onClick={() => setMobileMenu(false)}
        />
      )}
      <div className="workspace-body" inert={mobileMenu}>
        <header className="topbar">
          <div className="breadcrumb">
            <Button
              variant="icon"
              className="mobile-only"
              aria-label="Open navigation"
              aria-controls="workspace-navigation"
              aria-expanded={mobileMenu}
              onClick={() => setMobileMenu(true)}
            >
              <Icon name="menu" />
            </Button>
            <span>Workspace</span>
            <Icon name="chevron" size={13} />
            <strong>{nav.find((n) => n[0] === page)?.[2]}</strong>
          </div>
          <div className="topbar-right">
            <span className="avatar small">{user.displayName[0]}</span>
          </div>
        </header>
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
            {...shared}
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
      {toast && (
        <div className="toast" role="status">
          <Icon name="check" />
          <span>{toast}</span>
          <Button variant="icon" aria-label="Dismiss notification" onClick={() => setToast('')}>
            <Icon name="close" size={16} />
          </Button>
        </div>
      )}
      {pending && (
        <Modal title="Leave without saving?" onClose={() => setPending(null)}>
          <p>
            Your unsaved edits will be discarded. Save your changes first if you want to keep them.
          </p>
          <div className="actions">
            <Button variant="secondary" onClick={() => setPending(null)}>
              Keep editing
            </Button>
            <Button
              onClick={() => {
                const next = pending;
                setPending(null);
                setDirty(false);
                go(next.target, next.context);
              }}
            >
              Discard changes
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
