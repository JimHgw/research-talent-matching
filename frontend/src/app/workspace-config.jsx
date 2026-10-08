import { coreWorkspaceConfiguration } from './core-workspace-config.jsx';
import { withTagVocabulary } from './withTagVocabulary.jsx';
import OpportunitiesPage from '../features/opportunities/OpportunitiesPage.jsx';

const Opportunities = withTagVocabulary(OpportunitiesPage);

// Feature composition belongs here; the core shell remains independently usable.
export const workspaceConfiguration = Object.fromEntries(
  Object.entries(coreWorkspaceConfiguration).map(([role, definition]) => [
    role,
    {
      ...definition,
      navigation: [...definition.navigation, ['opportunities', 'briefcase', 'Opportunities']],
      pages: { ...definition.pages, opportunities: Opportunities },
    },
  ])
);
