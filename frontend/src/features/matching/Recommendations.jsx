import React, { useState } from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import { Button, Empty, ErrorNotice, Icon, Loading, Pager } from '../../shared/ui.jsx';
import MatchDetails from './MatchDetails.jsx';
import ProfileConfirmationRequired from '../../shared/ProfileConfirmationRequired.jsx';

function OpportunityCard({ opportunity, summary, rank, onView, onDetails, CollectionButton }) {
  const content = opportunity.content;
  const universityInitials = content.university
    .split(' ')
    .filter((word) => !['of', 'the'].includes(word.toLowerCase()))
    .map((word) => word[0])
    .join('')
    .slice(0, 3);
  return (
    <article className="recommendation-card">
      <div className="card-top">
        <span
          className={`university-mark ${content.disciplineGroup === 'BUSINESS' ? 'peach' : ''}`}
        >
          {universityInitials}
        </span>
        <div>
          <small>{content.university}</small>
          <span className="card-category">{content.disciplineGroup}</span>
        </div>
        {summary && (
          <span className="score-chip">
            {summary.score ?? '—'}
            <small>/100</small>
          </span>
        )}
      </div>
      <h3>{content.title}</h3>
      <p className="card-description">{content.description}</p>
      <div className="tag-row">
        <span>{content.discipline}</span>
        <span>{content.researchArea}</span>
      </div>
      {CollectionButton && <CollectionButton opportunityId={opportunity.id} />}
      <div className="card-bottom">
        <span className="muted">
          {rank ? `#${rank} recommendation` : `${content.requirements.length} requirements`}
        </span>
        <Button variant="text" onClick={onView}>
          {summary ? 'Why this match?' : 'View details'}
          <Icon name="arrow" size={16} />
        </Button>
        {onDetails && (
          <Button variant="text" onClick={onDetails}>
            View opportunity
            <Icon name="briefcase" size={16} />
          </Button>
        )}
      </div>
    </article>
  );
}

export default function Recommendations({ navigate, OpportunityDetails, CollectionButton }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState(null);
  const resource = useResource(() => api.recommendations(page), [page], true);
  return (
    <>
      <div className="section-title">
        <div>
          <h2>Your recommended opportunities</h2>
          <p>Ranked using your current confirmed profile.</p>
        </div>
        <span className="subtle-pill">{resource.data?.total ?? '—'} opportunities</span>
      </div>
      {resource.loading ? (
        <Loading />
      ) : resource.error?.code === 'PROFILE_UNCONFIRMED' ? (
        <ProfileConfirmationRequired onReview={() => navigate('profile')} />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : resource.data.items.length ? (
        <div className="card-grid">
          {resource.data.items.map((item) => (
            <OpportunityCard
              key={item.opportunity.id}
              opportunity={item.opportunity}
              summary={item.summary}
              rank={item.rank}
              CollectionButton={CollectionButton}
              onView={() => setSelected(item.opportunity.id)}
              onDetails={() => setDetails(item.opportunity.id)}
            />
          ))}
        </div>
      ) : (
        <Empty title="No opportunities just yet">
          Published opportunities will appear here when teams add them.
        </Empty>
      )}
      <Pager data={resource.data} onPage={setPage} />

      {resource.data && selected && (
        <MatchDetails
          opportunityId={selected}
          navigate={navigate}
          onClose={() => setSelected(null)}
        />
      )}
      {resource.data && details && OpportunityDetails && (
        <OpportunityDetails
          opportunityId={details}
          onClose={() => setDetails(null)}
          onMatch={() => {
            setDetails(null);
            setSelected(details);
          }}
        />
      )}
    </>
  );
}
