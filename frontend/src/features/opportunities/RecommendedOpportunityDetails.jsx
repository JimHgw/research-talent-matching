import RefreshStatus from '../../shared/RefreshStatus.jsx';
import { useDataInvalidation } from '../../shared/data-invalidation.js';
import { useLanguage } from '../../shared/i18n.jsx';
import React from 'react';
import { api } from '../../api/client.js';
import { useResource } from '../../shared/hooks.js';
import { Badge, Button, ErrorNotice, Icon, Loading, Modal } from '../../shared/ui.jsx';
import { requirementKinds } from './academic.js';
import OpportunityMetadata from './OpportunityMetadata.jsx';

export default function OpportunityDetails({ opportunityId, onClose, onMatch, CollectionButton }) {
  const { t } = useLanguage();
  const resource = useResource(
    ({ signal }) => api.opportunity(opportunityId, { signal }),
    [opportunityId],
    true,
    { retainData: true }
  );
  const opportunity = resource.data;
  useDataInvalidation(resource.refresh, ['opportunities']);
  return (
    <Modal title={t('Research opportunity')} onClose={onClose}>
      <RefreshStatus resource={resource} />
      {resource.initialLoading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorNotice error={resource.error} retry={resource.refresh} />
      ) : (
        <div className="opportunity-details">
          <div className="row-between">
            <span className="eyebrow">{opportunity.content.university}</span>
            <Badge
              status={opportunity.availabilityStatus === 'EXPIRED' ? 'EXPIRED' : opportunity.status}
            />
          </div>
          <h3>{opportunity.content.title}</h3>
          <div className="tag-row">
            <span>{t(opportunity.content.disciplineGroup)}</span>
            <span>{opportunity.content.discipline}</span>
            <span>{opportunity.content.researchArea}</span>
          </div>
          <p className="opportunity-description">{opportunity.content.description}</p>
          {opportunity.content.opportunityType && <p>{t(opportunity.content.opportunityType)}</p>}
          <OpportunityMetadata content={opportunity.content} />
          <h4>{t('Requirements')}</h4>
          {opportunity.content.requirements.length ? (
            <ul className="requirement-list">
              {opportunity.content.requirements.map((requirement) => (
                <li key={requirement.id}>
                  <strong>{requirement.label}</strong>
                  <span>
                    {requirement.importance === 'REQUIRED' ? t('Required') : t('Preferred')} ·{' '}
                    {t(requirementKinds[requirement.kind] || requirement.kind)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">{t('No requirements provided.')}</p>
          )}
          {CollectionButton && <CollectionButton opportunityId={opportunity.id} />}
          <div className="actions">
            <Button variant="secondary" onClick={onClose}>
              {t('Close')}
            </Button>
            <Button onClick={onMatch} disabled={opportunity.availabilityStatus === 'EXPIRED'}>
              {t('Why this match?')}
              <Icon name="arrow" size={16} />
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
