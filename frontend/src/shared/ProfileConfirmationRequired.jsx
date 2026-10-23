import { useLanguage } from './i18n.jsx';
import React from 'react';
import { Button, Empty, Icon } from './ui.jsx';

// Every owner matching entry returns to the same saved-profile review flow.
export default function ProfileConfirmationRequired({ onReview }) {
  const { t } = useLanguage();
  return (
    <Empty
      icon="user"
      title={t('Your profile needs a review')}
      action={
        onReview && (
          <Button onClick={onReview}>
            {t('Review my profile')}
            <Icon name="arrow" size={16} />
          </Button>
        )
      }
    >
      {t('Save and confirm your academic information before we compare it with opportunities.')}
    </Empty>
  );
}
