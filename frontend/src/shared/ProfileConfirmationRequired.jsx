import React from 'react';
import { Button, Empty, Icon } from './ui.jsx';

// Every owner matching entry returns to the same saved-profile review flow.
export default function ProfileConfirmationRequired({ onReview }) {
  return (
    <Empty
      icon="user"
      title="Your profile needs a review"
      action={
        onReview && (
          <Button onClick={onReview}>
            Review my profile
            <Icon name="arrow" size={16} />
          </Button>
        )
      }
    >
      Save and confirm your academic information before we compare it with opportunities.
    </Empty>
  );
}
