import React from 'react';
import { Brand, Button, Icon } from '../shared/ui.jsx';
import LanguageSelect from '../shared/LanguageSelect.jsx';
import { useLanguage } from '../shared/i18n.jsx';

export function WorkspaceSidebar({ user, team, nav, page, navigate, mobileMenu, setMobileMenu }) {
  const { t } = useLanguage();
  return (
    <>
      <aside id="workspace-navigation" className={`sidebar ${mobileMenu ? 'mobile-open' : ''}`}>
        <div className="sidebar-brand">
          <Brand />
          <Button
            variant="icon"
            className="mobile-only"
            aria-label={t('Close navigation')}
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
            <strong>{t(team ? 'Research team' : 'Talent workspace')}</strong>
            <small>{t('University research')}</small>
          </div>
        </div>
        <span className="nav-caption">{t('WORKSPACE')}</span>
        <nav aria-label={t('Main navigation')}>
          {nav.map(([key, icon, label]) => (
            <button
              key={key}
              className={page === key ? 'active' : ''}
              aria-current={page === key ? 'page' : undefined}
              onClick={() => navigate(key)}
            >
              <Icon name={icon} />
              <span>{t(label)}</span>
              {page === key && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Icon name="spark" />
            <strong>{t('Make discovery meaningful.')}</strong>
            <p>
              {t('Clear evidence.')}
              <br />
              {t('Better connections.')}
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
              <strong>
                <bdi>{user.displayName}</bdi>
              </strong>
              <small>{t(team ? 'Research team' : 'Research talent')}</small>
            </div>
            <Button variant="icon" aria-label={t('Sign out')} onClick={() => navigate('logout')}>
              <Icon name="logout" size={18} />
            </Button>
          </div>
        </div>
      </aside>
      {mobileMenu && (
        <button
          className="menu-backdrop"
          aria-label={t('Close navigation')}
          onClick={() => setMobileMenu(false)}
        />
      )}
    </>
  );
}

export function WorkspaceHeader({ user, nav, page, mobileMenu, setMobileMenu, onAccount }) {
  const { t } = useLanguage();
  return (
    <header className="topbar">
      <div className="breadcrumb">
        <Button
          variant="icon"
          className="mobile-only"
          aria-label={t('Open navigation')}
          aria-controls="workspace-navigation"
          aria-expanded={mobileMenu}
          onClick={() => setMobileMenu(true)}
        >
          <Icon name="menu" />
        </Button>
        <span>{t('Workspace')}</span>
        <Icon name="chevron" size={13} />
        <strong>{t(nav.find((n) => n[0] === page)?.[2] || '')}</strong>
      </div>
      <div className="topbar-right">
        <LanguageSelect />
        <Button
          variant="text"
          className="account-entry"
          aria-label={t('Account details')}
          onClick={onAccount}
        >
          <span>{t('Account ID')}</span>
          <code dir="ltr">{user.id}</code>
        </Button>
      </div>
    </header>
  );
}

export function WorkspaceToast({ toast, setToast }) {
  const { t } = useLanguage();
  return (
    <>
      {toast && (
        <div className="toast" role="status">
          <Icon name="check" />
          <span>{toast}</span>
          <Button
            variant="icon"
            aria-label={t('Dismiss notification')}
            onClick={() => setToast('')}
          >
            <Icon name="close" size={16} />
          </Button>
        </div>
      )}
    </>
  );
}
