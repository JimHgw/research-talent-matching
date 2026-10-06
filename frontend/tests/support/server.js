// Test double only. Never import this module from application code.
import { ApiError } from '../../src/api/errors.js';
import {
  createSeed,
  TEST_ACCOUNTS,
  TEST_PASSWORD,
  tags,
  SECTIONS,
  PROFILE_FIELDS,
} from './seed.js';
import { evaluate, isConfirmed, visibleProfile, rank } from './matching.js';

const STORAGE_KEY = 'test-fixture-state';
const clone = (value) => structuredClone(value);
const id = (prefix) => `${prefix}_${crypto.randomUUID()}`;
const publicOpportunity = ({ _ownerId, ...value }) => clone(value);
const publicDocument = ({ _ownerId, _queuedAt, _fail, ...value }) => clone(value);
function fail(status, code, message, fieldErrors = [], extra = {}) {
  throw new ApiError(status, {
    error: { code, message, fieldErrors, ...extra },
    requestId: id('request'),
  });
}
function invalid(message, field = '') {
  fail(422, 'VALIDATION_ERROR', message, field ? [{ field, message }] : []);
}
function checkRevision(actual, expected) {
  if (!Number.isInteger(expected) || expected < 0)
    invalid('A valid revision is required.', 'expectedRevision');
  if (actual !== expected)
    fail(
      409,
      'REVISION_CONFLICT',
      'This record changed. Reload the latest version before saving.',
      [],
      { currentRevision: actual }
    );
}
function tagCheck(tagId, kind) {
  if (!tags.some((t) => t.id === tagId && t.kind === kind))
    invalid('Choose an existing tag of the correct type.');
}
function unique(values) {
  return new Set(values).size === values.length;
}
function requiredText(value, label, max = 200) {
  if (typeof value !== 'string' || !value.trim() || value.length > max)
    invalid(`${label} is required (maximum ${max} characters).`);
}
function validateSections(content, partial = false) {
  if (!content || typeof content !== 'object' || Array.isArray(content))
    invalid('Profile content must be an object.');
  const allowed = partial ? SECTIONS : PROFILE_FIELDS;
  if (Object.keys(content).some((k) => !allowed.includes(k))) invalid('Unknown profile field.');
  if (partial && !Object.keys(content).length) invalid('Select at least one section to import.');
  if (!partial) {
    if (PROFILE_FIELDS.some((k) => !(k in content))) invalid('Send the complete profile content.');
    if (typeof content.displayName !== 'string' || content.displayName.length > 100)
      invalid('Name must be at most 100 characters.');
    if (![null, 'STEM', 'BUSINESS'].includes(content.disciplineGroup))
      invalid('Choose a valid discipline group.');
  }
  for (const section of SECTIONS.filter((k) => k in content)) {
    const items = content[section];
    if (!Array.isArray(items) || items.length > 100)
      invalid('Each profile section accepts at most 100 records.');
    if (section === 'skills') {
      if (!unique(items.map((s) => s.tagId))) invalid('Each skill can appear only once.');
      for (const skill of items) {
        tagCheck(skill.tagId, 'SKILL');
        if (!['HAS', 'DOES_NOT_HAVE'].includes(skill.claim)) invalid('Choose a valid skill claim.');
        if (typeof skill.evidenceText !== 'string' || skill.evidenceText.length > 2000)
          invalid('Skill evidence must be at most 2,000 characters.');
      }
    } else if (section === 'researchInterests') {
      if (!unique(items)) invalid('Interests cannot be repeated.');
      items.forEach((tag) => tagCheck(tag, 'INTEREST'));
    } else {
      if (!unique(items.map((item) => item.id))) invalid('Record identifiers must be unique.');
      for (const item of items) {
        if (typeof item.id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(item.id))
          invalid('Record identifier is invalid.');
        if (section === 'education') {
          requiredText(item.institution, 'Institution');
          requiredText(item.qualification, 'Qualification');
          for (const year of [item.startYear, item.endYear])
            if (year !== null && (!Number.isInteger(year) || year < 1900 || year > 2200))
              invalid('Enter a year between 1900 and 2200.');
          if (item.startYear && item.endYear && item.endYear < item.startYear)
            invalid('End year cannot precede start year.');
        } else if (section === 'courses') requiredText(item.name, 'Course name');
        else requiredText(item.title, 'Title', section === 'researchOutputs' ? 300 : 200);
        if (
          item.description !== undefined &&
          (typeof item.description !== 'string' || item.description.length > 5000)
        )
          invalid('Description must be at most 5,000 characters.');
        if (section === 'researchOutputs') {
          if (!['PUBLICATION', 'PROJECT', 'OTHER'].includes(item.type))
            invalid('Choose a valid output type.');
          if (item.url !== null) {
            try {
              if (!['http:', 'https:'].includes(new URL(item.url).protocol)) throw new Error();
            } catch {
              invalid('Output links must be valid HTTP or HTTPS URLs.');
            }
          }
        }
      }
    }
  }
}
function validateOpportunity(content, published) {
  if (!content) invalid('Opportunity content is required.');
  for (const key of ['title', 'university', 'discipline', 'researchArea', 'description'])
    requiredText(
      content[key],
      key,
      key === 'description' ? 10000 : key === 'researchArea' ? 300 : 200
    );
  if (!['STEM', 'BUSINESS'].includes(content.disciplineGroup)) invalid('Choose STEM or Business.');
  if (!Array.isArray(content.requirements) || content.requirements.length > 50)
    invalid('At most 50 requirements are allowed.');
  if (published && !content.requirements.length)
    invalid('Add at least one requirement before publishing.');
  if (!unique(content.requirements.map((r) => r.id)))
    invalid('Requirement identifiers must be unique.');
  for (const r of content.requirements) {
    requiredText(r.label, 'Requirement label', 300);
    if (
      !['SKILL', 'INTEREST'].includes(r.kind) ||
      !['REQUIRED', 'PREFERRED'].includes(r.importance)
    )
      invalid('Choose a valid requirement type and importance.');
    if (!Array.isArray(r.tagIds) || !r.tagIds.length || r.tagIds.length > 20 || !unique(r.tagIds))
      invalid('Choose 1–20 unique tags per requirement.');
    r.tagIds.forEach((tag) => tagCheck(tag, r.kind));
  }
}

export function createMockServer({ storage, now = () => Date.now(), processingDelay = 1600 } = {}) {
  let memory = createSeed();
  const files = new Map();
  function load() {
    if (storage) {
      try {
        const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || 'null');
        if (parsed?.version === 1) return parsed;
      } catch {
        /* A missing or damaged demo store starts with synthetic data. */
      }
    }
    return clone(memory);
  }
  function save(state) {
    if (storage) {
      try {
        storage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch {
        fail(
          500,
          'INTERNAL_ERROR',
          'Demo storage is full or unavailable. Your save could not be persisted.'
        );
      }
    }
    memory = clone(state);
  }
  function reset() {
    files.clear();
    memory = createSeed();
    save(memory);
  }
  async function dispatch(method, path, body) {
    const url = new URL(path, 'http://demo.local');
    const route = url.pathname;
    const state = load();
    const stamp = () => new Date(now()).toISOString();
    let user = TEST_ACCOUNTS.find((u) => u.id === state.sessionUserId);
    const session = () => ({
      user: user
        ? { id: user.id, email: user.email, displayName: user.displayName, role: user.role }
        : null,
      csrfToken: 'mock-session-token',
    });
    const role = (wanted) => {
      if (!user) fail(401, 'UNAUTHENTICATED', 'Please sign in to continue.');
      if (wanted && user.role !== wanted)
        fail(403, 'FORBIDDEN', 'This account cannot access that workspace.');
    };
    const notFound = () =>
      fail(404, 'NOT_FOUND', 'This item is unavailable. Refresh the list to continue.');
    const page = (items) => {
      const number = Number(url.searchParams.get('page') ?? 1);
      const size = Number(url.searchParams.get('pageSize') ?? 20);
      if (
        !Number.isInteger(number) ||
        number < 1 ||
        !Number.isInteger(size) ||
        size < 1 ||
        size > 100
      )
        invalid('Invalid pagination.');
      return {
        items: items.slice((number - 1) * size, number * size),
        page: number,
        pageSize: size,
        total: items.length,
      };
    };
    const profile = () => {
      role('TALENT');
      return state.profiles[user.id];
    };
    const confirmed = (p) => {
      if (!isConfirmed(p))
        fail(
          409,
          'PROFILE_UNCONFIRMED',
          'Review and confirm your current profile to see recommendations.'
        );
    };
    const unconfirm = (p) => {
      p.revision++;
      p.updatedAt = stamp();
      p.confirmation = { status: 'UNCONFIRMED', confirmedRevision: null, confirmedAt: null };
    };
    const result = (value) => {
      save(state);
      return clone(value);
    };

    if (route === '/auth/session' && method === 'GET') return session();
    if (route === '/auth/login' && method === 'POST') {
      user = TEST_ACCOUNTS.find((u) => u.email === body?.email?.trim().toLowerCase());
      if (!user || body?.password !== TEST_PASSWORD)
        fail(401, 'INVALID_CREDENTIALS', 'The email or password is incorrect.');
      state.sessionUserId = user.id;
      return result(session());
    }
    role();
    if (route === '/auth/logout' && method === 'POST') {
      state.sessionUserId = null;
      save(state);
      return;
    }
    if (route === '/tags' && method === 'GET') {
      const kind = url.searchParams.get('kind');
      if (kind && !['SKILL', 'INTEREST'].includes(kind)) invalid('Invalid tag kind.');
      return { items: clone(tags.filter((t) => !kind || t.kind === kind)) };
    }
    if (route === '/me/profile') {
      const p = profile();
      if (method === 'GET') return clone(p);
      if (method === 'PUT') {
        checkRevision(p.revision, body?.expectedRevision);
        validateSections(body.content);
        if (JSON.stringify(p.content) !== JSON.stringify(body.content)) {
          for (const origin of p.origins)
            if (
              JSON.stringify(p.content[origin.field]) !== JSON.stringify(body.content[origin.field])
            )
              Object.assign(origin, { sourceType: 'MANUAL', documentId: null });
          p.content = clone(body.content);
          unconfirm(p);
        }
        return result(p);
      }
    }
    if (route === '/me/profile/confirmation' && method === 'POST') {
      const p = profile();
      checkRevision(p.revision, body?.expectedRevision);
      if (!p.content.displayName.trim() || !SECTIONS.some((s) => p.content[s].length))
        invalid('Add your name and at least one academic or research section before confirming.');
      if (!isConfirmed(p)) {
        p.confirmation = {
          status: 'CONFIRMED',
          confirmedRevision: p.revision,
          confirmedAt: stamp(),
        };
        p.updatedAt = stamp();
      }
      return result(p);
    }
    if (route === '/me/privacy') {
      role('TALENT');
      const privacy = state.privacy[user.id];
      if (method === 'GET') return clone(privacy);
      if (method === 'PUT') {
        checkRevision(privacy.revision, body?.expectedRevision);
        if (
          typeof body.discoverable !== 'boolean' ||
          !Array.isArray(body.visibleFields) ||
          !unique(body.visibleFields) ||
          body.visibleFields.some((f) => !PROFILE_FIELDS.includes(f))
        )
          invalid('Choose valid visibility settings.');
        if (
          privacy.discoverable !== body.discoverable ||
          JSON.stringify(privacy.visibleFields) !== JSON.stringify(body.visibleFields)
        )
          Object.assign(privacy, {
            discoverable: body.discoverable,
            visibleFields: clone(body.visibleFields),
            revision: privacy.revision + 1,
            updatedAt: stamp(),
          });
        return result(privacy);
      }
    }
    if (route.startsWith('/me/documents')) {
      role('TALENT');
      const updateStatus = (d) => {
        if (['QUEUED', 'PROCESSING'].includes(d.status)) {
          const elapsed = now() - d._queuedAt;
          d.status =
            elapsed >= processingDelay
              ? d._fail
                ? 'FAILED'
                : 'READY'
              : elapsed > 0
                ? 'PROCESSING'
                : 'QUEUED';
          if (d.status === 'FAILED')
            d.error = {
              code: 'EXTRACTION_FAILED',
              message: 'Simulated extraction failure. You can enter your profile manually.',
              fieldErrors: [],
            };
          d.updatedAt = stamp();
        }
        return d;
      };
      if (route === '/me/documents' && method === 'GET')
        return result(
          page(
            state.documents
              .filter((d) => d._ownerId === user.id)
              .map(updateStatus)
              .sort((a, b) => b.createdAt.localeCompare(a.createdAt) || a.id.localeCompare(b.id))
              .map(publicDocument)
          )
        );
      if (route === '/me/documents' && method === 'POST') {
        const file = body?.get('file'),
          kind = body?.get('kind');
        if (!file || typeof file === 'string' || !file.size) invalid('Choose a non-empty file.');
        if (!['CV', 'TRANSCRIPT'].includes(kind)) invalid('Choose a document category.');
        if (file.size > 10485760)
          fail(413, 'UPLOAD_TOO_LARGE', 'Choose a file no larger than 10 MiB.');
        const extension = file.name.split('.').pop().toLowerCase();
        const mediaType = {
          pdf: 'application/pdf',
          docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }[extension];
        if (!mediaType) fail(415, 'UNSUPPORTED_FILE_TYPE', 'Only PDF and DOCX are supported.');
        const signature = new Uint8Array(await file.slice(0, 5).arrayBuffer());
        if (
          (extension === 'pdf' && String.fromCharCode(...signature) !== '%PDF-') ||
          (extension === 'docx' && !(signature[0] === 80 && signature[1] === 75))
        )
          fail(415, 'UNSUPPORTED_FILE_TYPE', 'The file contents do not match its extension.');
        const d = {
          id: id('doc'),
          kind,
          fileName: file.name,
          mediaType,
          sizeBytes: file.size,
          status: 'QUEUED',
          createdAt: stamp(),
          updatedAt: stamp(),
          error: null,
          _ownerId: user.id,
          _queuedAt: now(),
          _fail: file.name.toLowerCase().includes('fail'),
        };
        state.documents.push(d);
        files.set(d.id, file);
        return result(publicDocument(d));
      }
      const match = route.match(/^\/me\/documents\/([^/]+)(?:\/(extraction|apply|file))?$/);
      if (match) {
        const d = state.documents.find((doc) => doc.id === match[1] && doc._ownerId === user.id);
        if (!d) notFound();
        updateStatus(d);
        const action = match[2];
        if (!action && method === 'GET') return result(publicDocument(d));
        if (action === 'file' && method === 'GET') {
          if (!files.has(d.id))
            fail(
              404,
              'NOT_FOUND',
              'Original files are kept in memory in this demo. Upload again after reloading the page.'
            );
          return files.get(d.id);
        }
        if (
          (action === 'extraction' && method === 'GET') ||
          (action === 'apply' && method === 'POST')
        ) {
          if (d.status === 'FAILED') fail(422, 'EXTRACTION_FAILED', d.error.message);
          if (d.status !== 'READY')
            fail(409, 'EXTRACTION_NOT_READY', 'Extraction is still processing.');
          if (action === 'extraction')
            return result({
              documentId: d.id,
              status: 'READY',
              suggestedSections: {
                education: [
                  {
                    id: 'edu_imported',
                    institution: 'UNSW',
                    qualification: 'Master of IT',
                    discipline: 'Computer Science',
                    startYear: 2025,
                    endYear: null,
                  },
                ],
                skills: [
                  {
                    tagId: 'skill_python',
                    claim: 'HAS',
                    evidenceText:
                      'Synthetic suggestion for review. Replace this text with your own evidence.',
                  },
                ],
              },
              uncertainFields: [
                {
                  field: 'researchOutputs',
                  status: 'NOT_RECOGNISED',
                  reason: 'No real document extraction runs in demo mode.',
                },
              ],
              warnings: [
                'DEMO: these fixed suggestions are not extracted from your file. Review and edit before importing.',
              ],
              reviewRequired: true,
            });
          const p = profile();
          checkRevision(p.revision, body?.expectedProfileRevision);
          validateSections(body.sections, true);
          Object.assign(p.content, clone(body.sections));
          for (const origin of p.origins)
            if (origin.field in body.sections)
              Object.assign(origin, { sourceType: 'USER_REVIEWED_DOCUMENT', documentId: d.id });
          unconfirm(p);
          return result(p);
        }
      }
    }
    if (route === '/opportunities') {
      if (method === 'GET') {
        const scope = url.searchParams.get('scope') || 'published';
        if (!['mine', 'published'].includes(scope)) invalid('Choose a valid list scope.');
        if (scope === 'mine') role('RESEARCH_TEAM');
        return page(
          state.opportunities
            .filter((o) => (scope === 'mine' ? o._ownerId === user.id : o.status === 'PUBLISHED'))
            .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt) || a.id.localeCompare(b.id))
            .map(publicOpportunity)
        );
      }
      if (method === 'POST') {
        role('RESEARCH_TEAM');
        validateOpportunity(body, false);
        const o = {
          id: id('opp'),
          revision: 1,
          status: 'DRAFT',
          content: clone(body),
          createdAt: stamp(),
          updatedAt: stamp(),
          _ownerId: user.id,
        };
        state.opportunities.push(o);
        return result(publicOpportunity(o));
      }
    }
    const opportunityRoute = route.match(
      /^\/opportunities\/([^/]+)(?:\/(publish|talent-matches)(?:\/([^/]+))?)?$/
    );
    if (opportunityRoute) {
      const [, opportunityId, action, talentId] = opportunityRoute;
      const o = state.opportunities.find((item) => item.id === opportunityId);
      if (!o) notFound();
      if (!action && method === 'GET') {
        if (o.status !== 'PUBLISHED' && o._ownerId !== user.id) notFound();
        return publicOpportunity(o);
      }
      role('RESEARCH_TEAM');
      if (o._ownerId !== user.id) notFound();
      if (!action && method === 'PUT') {
        checkRevision(o.revision, body?.expectedRevision);
        validateOpportunity(body.content, o.status === 'PUBLISHED');
        if (JSON.stringify(o.content) !== JSON.stringify(body.content)) {
          o.content = clone(body.content);
          o.revision++;
          o.updatedAt = stamp();
        }
        return result(publicOpportunity(o));
      }
      if (action === 'publish' && method === 'POST') {
        checkRevision(o.revision, body?.expectedRevision);
        validateOpportunity(o.content, true);
        if (o.status === 'DRAFT') {
          o.status = 'PUBLISHED';
          o.revision++;
          o.updatedAt = stamp();
        }
        return result(publicOpportunity(o));
      }
      if (action === 'talent-matches' && method === 'GET') {
        if (o.status !== 'PUBLISHED') notFound();
        const eligible = Object.values(state.profiles).filter(
          (p) => isConfirmed(p) && state.privacy[p.talentId].discoverable
        );
        const make = (p) => ({
          talent: visibleProfile(p, state.privacy[p.talentId]),
          ...evaluate(o, p, state.privacy[p.talentId].visibleFields),
        });
        if (talentId) {
          const p = eligible.find((p) => p.talentId === talentId);
          if (!p) notFound();
          return {
            opportunityId: o.id,
            opportunityRevision: o.revision,
            ...make(p),
            evaluatedAt: stamp(),
          };
        }
        return page(
          rank(
            eligible.map((p) => {
              const { requirements, ...item } = make(p);
              return item;
            }),
            (x) => x.talent.talentId
          )
        );
      }
    }
    if (route === '/me/recommendations' && method === 'GET') {
      const p = profile();
      confirmed(p);
      return page(
        rank(
          state.opportunities
            .filter((o) => o.status === 'PUBLISHED')
            .map((o) => ({ opportunity: publicOpportunity(o), summary: evaluate(o, p).summary })),
          (x) => x.opportunity.id
        )
      );
    }
    const ownerMatch = route.match(/^\/me\/opportunity-matches\/([^/]+)$/);
    if (ownerMatch && method === 'GET') {
      const p = profile();
      confirmed(p);
      const o = state.opportunities.find(
        (item) => item.id === ownerMatch[1] && item.status === 'PUBLISHED'
      );
      if (!o) notFound();
      return {
        opportunity: publicOpportunity(o),
        profileRevision: p.revision,
        ...evaluate(o, p),
        evaluatedAt: stamp(),
      };
    }
    notFound();
  }
  return { dispatch, reset };
}
