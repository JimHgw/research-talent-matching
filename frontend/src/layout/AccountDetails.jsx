import React from 'react';
import { Button, Modal } from '../shared/ui.jsx';
import { useLanguage } from '../shared/i18n.jsx';

export default function AccountDetails({ user, onClose, onSwitch }) {
  const { t } = useLanguage();
  return (
    <Modal title={t('Account details')} onClose={onClose}>
      <dl className="account-details">
        <dt>{t('Display name')}</dt>
        <dd>
          <bdi>{user.displayName}</bdi>
        </dd>
        <dt>{t('Email address')}</dt>
        <dd>
          <bdi dir="ltr">{user.email}</bdi>
        </dd>
        <dt>{t('Account ID')}</dt>
        <dd>
          <code dir="ltr">{user.id}</code>
        </dd>
        <dt>{t('Account type')}</dt>
        <dd>{t(user.role === 'RESEARCH_TEAM' ? 'Research team' : 'Research talent')}</dd>
      </dl>
      <p>{t('Use this ID or your email address to sign in.')}</p>
      <p className="muted">
        {t('To use another role, sign in with an account registered for that role.')}
      </p>
      <Button variant="secondary" onClick={onSwitch}>
        {t('Switch account')}
      </Button>
    </Modal>
  );
}
