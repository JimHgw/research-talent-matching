import React from 'react';
import { api } from '../api/client.js';
import { useResource } from '../shared/hooks.js';
import { ErrorNotice, Loading } from '../shared/ui.jsx';

// Attach the vocabulary dependency only to editors that need it.
export function withTagVocabulary(Page) {
  return function VocabularyPage(props) {
    const vocabulary = useResource(api.tags);
    if (vocabulary.loading) return <Loading />;
    if (vocabulary.error)
      return <ErrorNotice error={vocabulary.error} retry={vocabulary.refresh} />;
    return <Page {...props} tags={vocabulary.data?.items || []} />;
  };
}
