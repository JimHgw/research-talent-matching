import { coreWorkspaceConfiguration } from './core-workspace-config.jsx';
import { withTagVocabulary } from './withTagVocabulary.jsx';
import TeamOpportunities from '../features/opportunities/TeamOpportunities.jsx';
import OpportunityDetails from '../features/opportunities/RecommendedOpportunityDetails.jsx';
import OpportunitiesPage from '../features/opportunities/OpportunitiesPage.jsx';
import Recommendations from '../features/matching/Recommendations.jsx';
import TalentPage from '../features/matching/TalentPage.jsx';

const OpportunityManager = withTagVocabulary(TeamOpportunities);
const OpportunityBrowser = withTagVocabulary(OpportunitiesPage);

export const workspaceConfiguration = {
  TALENT: {
    ...coreWorkspaceConfiguration.TALENT,
    navigation: [
      ...coreWorkspaceConfiguration.TALENT.navigation.slice(0, 2),
      ['opportunities', 'briefcase', 'Opportunities'],
      ['recommendations', 'compass', 'Recommended opportunities'],
      ...coreWorkspaceConfiguration.TALENT.navigation.slice(2),
    ],
    pages: {
      ...coreWorkspaceConfiguration.TALENT.pages,
      opportunities: OpportunityBrowser,
      recommendations: Recommendations,
    },
    pageProps: {
      ...coreWorkspaceConfiguration.TALENT.pageProps,
      profile: { canRecommend: true },
      recommendations: { OpportunityDetails },
    },
  },
  RESEARCH_TEAM: {
    ...coreWorkspaceConfiguration.RESEARCH_TEAM,
    navigation: [
      ...coreWorkspaceConfiguration.RESEARCH_TEAM.navigation,
      ['opportunities', 'briefcase', 'Opportunities'],
      ['teamOpportunities', 'briefcase', 'My opportunities'],
      ['talent', 'user', 'Discover talent'],
    ],
    pages: {
      ...coreWorkspaceConfiguration.RESEARCH_TEAM.pages,
      opportunities: OpportunityBrowser,
      teamOpportunities: OpportunityManager,
      talent: TalentPage,
    },
  },
};
