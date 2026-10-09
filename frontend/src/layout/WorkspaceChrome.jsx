import React from 'react';
import { Brand, Button, Icon } from '../shared/ui.jsx';

export function WorkspaceSidebar({ user, team, nav, page, navigate, mobileMenu, setMobileMenu }) {
  return (
    <>
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
    </>
  );
}

export function WorkspaceHeader({ user, nav, page, mobileMenu, setMobileMenu }) {
  return (
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
  );
}

export function WorkspaceToast({ toast, setToast }) {
  return (
    <>
      {toast && (
        <div className="toast" role="status">
          <Icon name="check" />
          <span>{toast}</span>
          <Button variant="icon" aria-label="Dismiss notification" onClick={() => setToast('')}>
            <Icon name="close" size={16} />
          </Button>
        </div>
      )}
    </>
  );
}
