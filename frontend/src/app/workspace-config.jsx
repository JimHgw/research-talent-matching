import React from 'react';
import { coreWorkspaceConfiguration } from './core-workspace-config.jsx';
import { withTagVocabulary } from './withTagVocabulary.jsx';
import TeamOpportunities from '../features/opportunities/TeamOpportunities.jsx';
import OpportunityDetails from '../features/opportunities/RecommendedOpportunityDetails.jsx';
import OpportunitiesPage from '../features/opportunities/OpportunitiesPage.jsx';
import Recommendations from '../features/matching/Recommendations.jsx';
import TalentPage from '../features/matching/TalentPage.jsx';
import SavedOpportunities from '../features/collections/SavedOpportunities.jsx';
import CollectionButton from '../features/collections/CollectionButton.jsx';
import MatchDetails from '../features/matching/MatchDetails.jsx';

function SavedOpportunityDetails(props) {
  return <OpportunityDetails {...props} CollectionButton={CollectionButton} />;
}

const OpportunityManager = withTagVocabulary(TeamOpportunities);
const OpportunityBrowser = withTagVocabulary(OpportunitiesPage);
const TalentDiscovery = withTagVocabulary(TalentPage);

export const workspaceConfiguration = {
  TALENT: {
    ...coreWorkspaceConfiguration.TALENT,
    navigation: [
      ...coreWorkspaceConfiguration.TALENT.navigation.slice(0, 2),
      ['opportunities', 'briefcase', 'Opportunities'],
      ['recommendations', 'compass', 'Recommended opportunities'],
      ['saved', 'briefcase', 'Saved opportunities'],
      ...coreWorkspaceConfiguration.TALENT.navigation.slice(2),
    ],
    pages: {
      ...coreWorkspaceConfiguration.TALENT.pages,
      opportunities: OpportunityBrowser,
      recommendations: Recommendations,
      saved: SavedOpportunities,
    },
    pageProps: {
      ...coreWorkspaceConfiguration.TALENT.pageProps,
      profile: { canRecommend: true },
      recommendations: { OpportunityDetails: SavedOpportunityDetails, CollectionButton },
      saved: { OpportunityDetails: SavedOpportunityDetails, MatchDetails },
    },
  },
  RESEARCH_TEAM: {
    ...coreWorkspaceConfiguration.RESEARCH_TEAM,
    navigation: [
      ...coreWorkspaceConfiguration.RESEARCH_TEAM.navigation,
      ['opportunities', 'briefcase', 'Opportunities'],
      ['teamOpportunities', 'briefcase', 'My opportunities'],
      ['talent', 'user', 'Discover talent'],
      ['shortlists', 'user', 'Shortlisted candidates'],
    ],
    pages: {
      ...coreWorkspaceConfiguration.RESEARCH_TEAM.pages,
      opportunities: OpportunityBrowser,
      teamOpportunities: OpportunityManager,
      talent: TalentDiscovery,
      shortlists: TalentDiscovery,
    },
    pageProps: {
      talent: { CollectionButton },
      shortlists: { initialShortlist: true, CollectionButton },
    },
  },
};
