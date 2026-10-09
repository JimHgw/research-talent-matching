import { coreWorkspaceConfiguration } from './core-workspace-config.jsx';
import { withTagVocabulary } from './withTagVocabulary.jsx';
import TeamOpportunities from '../features/opportunities/TeamOpportunities.jsx';
import OpportunityDetails from '../features/opportunities/OpportunityDetails.jsx';
import Recommendations from '../features/matching/Recommendations.jsx';
import TalentPage from '../features/matching/TalentPage.jsx';

const OpportunityManager = withTagVocabulary(TeamOpportunities);

export const workspaceConfiguration = {
  TALENT: {
    ...coreWorkspaceConfiguration.TALENT,
    navigation: [
      ...coreWorkspaceConfiguration.TALENT.navigation.slice(0, 2),
      ['recommendations', 'compass', 'Opportunities'],
      ...coreWorkspaceConfiguration.TALENT.navigation.slice(2),
    ],
    pages: { ...coreWorkspaceConfiguration.TALENT.pages, recommendations: Recommendations },
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
      ['opportunities', 'briefcase', 'My opportunities'],
      ['talent', 'user', 'Discover talent'],
    ],
    pages: {
      ...coreWorkspaceConfiguration.RESEARCH_TEAM.pages,
      opportunities: OpportunityManager,
      talent: TalentPage,
    },
  },
};
