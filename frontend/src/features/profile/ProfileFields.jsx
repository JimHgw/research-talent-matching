import React from 'react';
import { Button, Field, Icon } from '../../shared/ui.jsx';
import { labels } from '../../shared/profile-labels.js';

const fieldConfigs = {
  education: [
    ['institution', 'Institution', 'text', true],
    ['qualification', 'Qualification', 'text', true],
    ['discipline', 'Discipline', 'text'],
    ['startYear', 'Start year', 'number'],
    ['endYear', 'End year', 'number'],
  ],
  courses: [
    ['name', 'Course name', 'text', true],
    ['code', 'Course code', 'text'],
    ['description', 'Description', 'textarea'],
  ],
  researchExperience: [
    ['title', 'Project / role title', 'text', true],
    ['organisation', 'Organisation', 'text'],
    ['description', 'Description', 'textarea'],
  ],
  researchOutputs: [
    ['title', 'Output title', 'text', true],
    ['type', 'Type', 'outputType'],
    ['url', 'Link (optional)', 'url'],
    ['description', 'Description', 'textarea'],
  ],
};
export default function ProfileFields({
  content,
  onChange,
  tags,
  sections = Object.keys(fieldConfigs).concat(['skills', 'researchInterests']),
  identity = true,
}) {
  const set = (key, value) => onChange({ ...content, [key]: value });
  const addRecord = (key) => {
    const row = { id: `record_${crypto.randomUUID()}` };
    for (const [field, , type] of fieldConfigs[key])
      row[field] =
        type === 'number' || field === 'url' || field === 'code'
          ? null
          : type === 'outputType'
            ? 'PROJECT'
            : '';
    set(key, [...(content[key] || []), row]);
  };
  return (
    <div className="profile-fields">
      {identity && (
        <section className="panel">
          <div className="section-heading">
            <span className="section-number">01</span>
            <h3>The basics</h3>
          </div>
          <div className="form-grid">
            <Field label="Display name">
              <input
                maxLength={100}
                value={content.displayName}
                onChange={(e) => set('displayName', e.target.value)}
                placeholder="Your name"
              />
            </Field>
            <Field label="Discipline group">
              <select
                value={content.disciplineGroup || ''}
                onChange={(e) => set('disciplineGroup', e.target.value || null)}
              >
                <option value="">Choose a group</option>
                <option value="STEM">STEM</option>
                <option value="BUSINESS">Business</option>
              </select>
            </Field>
          </div>
        </section>
      )}
      {sections.map((section, index) => (
        <section className="panel" key={section}>
          <div className="section-heading">
            <span className="section-number">
              {String(index + (identity ? 2 : 1)).padStart(2, '0')}
            </span>
            <h3>{labels[section]}</h3>
            <span className="muted count">{(content[section] || []).length} entries</span>
          </div>
          {section === 'skills' ? (
            <>
              <p className="help">
                Add skills you can support. Only use “Not yet” when you explicitly know you do not
                have that skill.
              </p>
              {(content.skills || []).map((skill, i) => (
                <div className="record" key={i}>
                  <div className="form-grid skill-grid">
                    <Field label="Skill">
                      <select
                        value={skill.tagId}
                        onChange={(e) =>
                          set(
                            'skills',
                            content.skills.map((s, n) =>
                              n === i ? { ...s, tagId: e.target.value } : s
                            )
                          )
                        }
                      >
                        {tags
                          .filter((t) => t.kind === 'SKILL')
                          .map((t) => (
                            <option
                              key={t.id}
                              value={t.id}
                              disabled={content.skills.some((s, n) => n !== i && s.tagId === t.id)}
                            >
                              {t.label}
                            </option>
                          ))}
                      </select>
                    </Field>
                    <Field label="Your experience">
                      <select
                        value={skill.claim}
                        onChange={(e) =>
                          set(
                            'skills',
                            content.skills.map((s, n) =>
                              n === i ? { ...s, claim: e.target.value } : s
                            )
                          )
                        }
                      >
                        <option value="HAS">I have this skill</option>
                        <option value="DOES_NOT_HAVE">Not yet — explicit gap</option>
                      </select>
                    </Field>
                    <Button
                      variant="icon"
                      aria-label={`Remove skill ${i + 1}`}
                      onClick={() =>
                        set(
                          'skills',
                          content.skills.filter((_, n) => n !== i)
                        )
                      }
                    >
                      <Icon name="close" />
                    </Button>
                  </div>
                  <Field label="Supporting evidence">
                    <textarea
                      rows={2}
                      maxLength={2000}
                      placeholder="A project, course, or experience that supports your statement"
                      value={skill.evidenceText}
                      onChange={(e) =>
                        set(
                          'skills',
                          content.skills.map((s, n) =>
                            n === i ? { ...s, evidenceText: e.target.value } : s
                          )
                        )
                      }
                    />
                  </Field>
                </div>
              ))}
              <Button
                variant="secondary"
                disabled={tags
                  .filter((t) => t.kind === 'SKILL')
                  .every((t) => (content.skills || []).some((s) => s.tagId === t.id))}
                onClick={() =>
                  set('skills', [
                    ...(content.skills || []),
                    {
                      tagId: tags.find(
                        (t) =>
                          t.kind === 'SKILL' &&
                          !(content.skills || []).some((s) => s.tagId === t.id)
                      ).id,
                      claim: 'HAS',
                      evidenceText: '',
                    },
                  ])
                }
              >
                <Icon name="plus" size={16} />
                Add skill
              </Button>
            </>
          ) : section === 'researchInterests' ? (
            <div className="tag-options">
              {tags
                .filter((t) => t.kind === 'INTEREST')
                .map((tag) => (
                  <label
                    className={`tag-option ${(content.researchInterests || []).includes(tag.id) ? 'selected' : ''}`}
                    key={tag.id}
                  >
                    <input
                      type="checkbox"
                      checked={(content.researchInterests || []).includes(tag.id)}
                      onChange={(e) =>
                        set(
                          'researchInterests',
                          e.target.checked
                            ? [...(content.researchInterests || []), tag.id]
                            : content.researchInterests.filter((id) => id !== tag.id)
                        )
                      }
                    />
                    {tag.label}
                  </label>
                ))}
            </div>
          ) : (
            <>
              {(content[section] || []).map((row, i) => (
                <div className="record" key={row.id}>
                  <div className="record-heading">
                    <strong>Record {i + 1}</strong>
                    <Button
                      variant="icon"
                      aria-label={`Remove ${labels[section]} record ${i + 1}`}
                      onClick={() =>
                        set(
                          section,
                          content[section].filter((_, n) => n !== i)
                        )
                      }
                    >
                      <Icon name="close" size={17} />
                    </Button>
                  </div>
                  <div className="form-grid">
                    {fieldConfigs[section].map(([field, label, type, required]) => (
                      <Field key={field} label={label + (required ? ' *' : '')}>
                        {type === 'outputType' ? (
                          <select
                            value={row[field]}
                            onChange={(e) =>
                              set(
                                section,
                                content[section].map((r, n) =>
                                  n === i ? { ...r, [field]: e.target.value } : r
                                )
                              )
                            }
                          >
                            <option value="PUBLICATION">Publication</option>
                            <option value="PROJECT">Project</option>
                            <option value="OTHER">Other</option>
                          </select>
                        ) : (
                          React.createElement(type === 'textarea' ? 'textarea' : 'input', {
                            type: type === 'textarea' ? undefined : type,
                            rows: type === 'textarea' ? 3 : undefined,
                            required,
                            maxLength:
                              type === 'textarea'
                                ? 5000
                                : field === 'title' && section === 'researchOutputs'
                                  ? 300
                                  : 200,
                            min: type === 'number' ? 1900 : undefined,
                            max: type === 'number' ? 2200 : undefined,
                            value: row[field] ?? '',
                            onChange: (e) =>
                              set(
                                section,
                                content[section].map((r, n) =>
                                  n === i
                                    ? {
                                        ...r,
                                        [field]:
                                          type === 'number'
                                            ? e.target.value === ''
                                              ? null
                                              : Number(e.target.value)
                                            : ['url', 'code'].includes(field) && !e.target.value
                                              ? null
                                              : e.target.value,
                                      }
                                    : r
                                )
                              ),
                          })
                        )}
                      </Field>
                    ))}
                  </div>
                </div>
              ))}
              <Button
                variant="secondary"
                disabled={(content[section] || []).length >= 100}
                onClick={() => addRecord(section)}
              >
                <Icon name="plus" size={16} />
                Add {labels[section].toLowerCase()}
              </Button>
            </>
          )}
        </section>
      ))}
    </div>
  );
}
