import React from 'react';
import ProfilePage from '../features/profile/ProfilePage.jsx';
import PrivacyPage from '../features/privacy/PrivacyPage.jsx';
import DocumentsPage from '../features/documents/DocumentsPage.jsx';
import { withTagVocabulary } from './withTagVocabulary.jsx';

const ProfileEditor = withTagVocabulary(ProfilePage);
const DocumentEditor = withTagVocabulary(DocumentsPage);

function AccountOverview({ user }) {
  return (
    <section className="panel">
      <h2>Your account</h2>
      <p>Signed in as {user.displayName}.</p>
      <p className="muted">Research team workspace</p>
    </section>
  );
}

// Tasks 18, 21 and 22 can run without importing opportunity or matching pages.
export const coreWorkspaceConfiguration = {
  TALENT: {
    defaultPage: 'profile',
    navigation: [
      ['profile', 'user', 'My profile'],
      ['documents', 'file', 'My documents'],
      ['privacy', 'shield', 'Privacy & visibility'],
    ],
    pages: { profile: ProfileEditor, documents: DocumentEditor, privacy: PrivacyPage },
    pageProps: { profile: { canRecommend: false } },
  },
  RESEARCH_TEAM: {
    defaultPage: 'overview',
    navigation: [['overview', 'grid', 'Overview']],
    pages: { overview: AccountOverview },
  },
};
