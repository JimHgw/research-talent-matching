import test from 'node:test';
import assert from 'node:assert/strict';
import {
  act,
  state,
  createMockServer,
  mount,
  click,
  change,
  field,
  checkbox,
  text,
  json,
} from './support/app-harness.js';

async function documents(names = ['review.pdf'], ready = true) {
  let now = Date.now();
  state.server = createMockServer({ now: () => now });
  await state.server.dispatch('POST', '/auth/login', {
    email: 'talent@example.test',
    password: 'Demo1234!',
  });
  const uploaded = [];
  for (const name of names) {
    const body = new FormData();
    body.append('file', new File(['%PDF-test-only'], name, { type: 'application/pdf' }));
    body.append('kind', 'CV');
    uploaded.push(await state.server.dispatch('POST', '/me/documents', body));
  }
  if (ready) now += 4000;
  await mount();
  await click('My documents');
  return uploaded;
}

async function review(name = 'review.pdf') {
  const row = [...document.querySelectorAll('.document-row')].find((row) =>
    row.textContent.includes(name)
  );
  assert.ok(row);
  await act(async () =>
    [...row.querySelectorAll('button')]
      .find((b) => b.textContent.trim() === 'Review suggestions')
      .click()
  );
}

function dialogButton(name) {
  const found = [...document.querySelectorAll('dialog button')].find(
    (button) => button.textContent.trim() === name || button.getAttribute('aria-label') === name
  );
  assert.ok(found, `Missing dialog button: ${name}`);
  return found;
}
const dialogClick = (name) => act(async () => dialogButton(name).click());

test('READY review is bound to the selected document and needs no recording state', async () => {
  const [first, second] = await documents(['first.pdf', 'second.pdf']);
  await review('second.pdf');
  assert.match(document.querySelector('dialog').textContent, /second.pdf/);
  assert.doesNotMatch(document.querySelector('dialog').textContent, /not-recording|first.pdf/);
  assert.equal(
    state.requests.filter((r) => r.path === `/me/documents/${second.id}/extraction`).length,
    1
  );
  assert.equal(
    state.requests.some((r) => r.path === `/me/documents/${first.id}/extraction`),
    false
  );
  assert.equal(dialogButton('Apply reviewed sections').disabled, true);
});

test('queued documents explain progress and cannot open suggestions prematurely', async () => {
  await documents(['waiting.pdf'], false);
  assert.match(text(), /Waiting for document processing/);
  assert.equal(
    [...document.querySelectorAll('button')].some(
      (b) => b.textContent.trim() === 'Review suggestions'
    ),
    false
  );
  await click('Enter details manually');
  assert.match(text(), /Tell your research story/);
});

test('a stale READY row handles not-ready review with an explicit check and recovers', async () => {
  await documents();
  let pending = true;
  state.intercept = (path) =>
    path.endsWith('/extraction') && pending
      ? json({ error: { code: 'EXTRACTION_NOT_READY', message: 'Still processing.' } }, 409)
      : null;
  await review();
  assert.match(document.querySelector('dialog').textContent, /still being processed/);
  assert.equal(document.querySelector('dialog form'), null);
  pending = false;
  await dialogClick('Check again');
  assert.equal(dialogButton('Apply reviewed sections').disabled, true);
  assert.equal(document.querySelector('[role="alert"]'), null);
});

test('failed review offers another upload or manual entry without an import form', async () => {
  await documents();
  state.intercept = (path) =>
    path.endsWith('/extraction')
      ? json({ error: { code: 'EXTRACTION_FAILED', message: 'Cannot extract this file.' } }, 422)
      : null;
  await review();
  assert.ok(dialogButton('Upload another document'));
  assert.equal(document.querySelector('dialog form'), null);
  await dialogClick('Continue with manual entry');
  assert.equal(document.querySelector('dialog'), null);
  assert.match(text(), /Tell your research story/);
});

test('empty extraction gives a useful manual-entry fallback and never sends an empty import', async () => {
  const [file] = await documents();
  state.intercept = (path) =>
    path.endsWith('/extraction')
      ? json({
          documentId: file.id,
          status: 'READY',
          suggestedSections: {},
          warnings: [],
          uncertainFields: [],
          reviewRequired: true,
        })
      : null;
  await review();
  assert.match(document.querySelector('dialog').textContent, /No structured suggestions/);
  assert.equal(document.querySelector('dialog form'), null);
  await dialogClick('Continue with manual entry');
  assert.match(text(), /Tell your research story/);
  assert.equal(
    state.requests.some((r) => r.path.endsWith('/apply')),
    false
  );
});

test('an extraction response for another document is rejected before exposing suggestions', async () => {
  await documents();
  state.intercept = async (path) => {
    if (!path.endsWith('/extraction')) return null;
    const extracted = await state.server.dispatch('GET', path);
    return json({
      ...extracted,
      documentId: 'doc_wrong',
      suggestedSections: {
        skills: [
          { id: 'skill_python', title: 'Python', evidenceText: 'WRONG DOCUMENT PRIVATE TEXT' },
        ],
      },
    });
  };
  await review();
  assert.match(document.querySelector('dialog').textContent, /did not match this document/);
  assert.doesNotMatch(document.querySelector('dialog').textContent, /WRONG DOCUMENT PRIVATE TEXT/);
  assert.equal(document.querySelector('dialog form'), null);
});

test('corrected suggestions survive cancelled close and reload, then explicit reload resets acknowledgement', async () => {
  await documents();
  await review();
  await change('Supporting evidence', 'Keep this reviewed correction');
  await checkbox('I understand that importing replaces');
  await dialogClick('Cancel');
  assert.equal(field('Supporting evidence').value, 'Keep this reviewed correction');
  await dialogClick('Reload suggestions');
  assert.equal(field('Supporting evidence').value, 'Keep this reviewed correction');
  window.confirm = () => true;
  await dialogClick('Reload suggestions');
  assert.notEqual(field('Supporting evidence').value, 'Keep this reviewed correction');
  assert.equal(dialogButton('Apply reviewed sections').disabled, true);
  assert.equal(
    state.requests.some((r) => r.path.endsWith('/apply')),
    false
  );
});

test('a revision conflict preserves corrections but blocks stale repeated import', async () => {
  await documents();
  await review();
  await change('Supporting evidence', 'Corrected before conflict');
  await checkbox('I understand that importing replaces');
  state.intercept = (path) =>
    path.endsWith('/apply')
      ? json({ error: { code: 'REVISION_CONFLICT', message: 'Profile changed.' } }, 409)
      : null;
  await dialogClick('Apply reviewed sections');
  assert.equal(field('Supporting evidence').value, 'Corrected before conflict');
  assert.equal(dialogButton('Apply reviewed sections').disabled, true);
  assert.ok(dialogButton('Review latest profile'));
  await dialogClick('Apply reviewed sections');
  assert.equal(state.requests.filter((r) => r.path.endsWith('/apply')).length, 1);
});

test('changing a reviewed suggestion or selection requires a fresh acknowledgement', async () => {
  await documents();
  await review();
  await checkbox('I understand that importing replaces');
  assert.equal(dialogButton('Apply reviewed sections').disabled, false);
  await change('Supporting evidence', 'A new correction after acknowledgement');
  assert.equal(dialogButton('Apply reviewed sections').disabled, true);
  await checkbox('I understand that importing replaces');
  await checkbox('Education');
  assert.equal(dialogButton('Apply reviewed sections').disabled, true);
});

test('a committed import with an invalid success response requires checking the saved profile', async () => {
  await documents();
  await review();
  await change('Supporting evidence', 'Correction saved by the server');
  await checkbox('I understand that importing replaces');
  state.intercept = async (path, options, body) => {
    if (!path.endsWith('/apply')) return null;
    const saved = await state.server.dispatch(options.method, path, body);
    return json({ ...saved, revision: 'unreadable' });
  };
  await dialogClick('Apply reviewed sections');
  assert.match(text(), /The request may have succeeded/);
  assert.equal(field('Supporting evidence').value, 'Correction saved by the server');
  assert.equal(dialogButton('Apply reviewed sections').disabled, true);
  assert.equal(dialogButton('Reload suggestions').disabled, true);
  await dialogClick('Apply reviewed sections');
  await dialogClick('Review latest profile');
  assert.ok(document.querySelector('dialog'));
  window.confirm = () => true;
  await dialogClick('Review latest profile');
  assert.equal(document.querySelector('dialog'), null);
  assert.match(text(), /Needs confirmation/);
  assert.equal(field('Supporting evidence').value, 'Correction saved by the server');
  assert.equal(state.requests.filter((r) => r.path.endsWith('/apply')).length, 1);
});

test('a late document read cannot replace the next review or its draft', async () => {
  const [first] = await documents(['first.pdf', 'second.pdf']);
  let finish;
  state.intercept = async (path) => {
    if (path !== `/me/documents/${first.id}/extraction`) return null;
    const result = await state.server.dispatch('GET', path);
    result.suggestedSections.skills[0].evidenceText = 'LATE FIRST DOCUMENT';
    return new Promise((resolve) => {
      finish = () => resolve(json(result));
    });
  };
  await review('first.pdf');
  await dialogClick('Close dialog');
  await review('second.pdf');
  await change('Supporting evidence', 'Keep the second document draft');
  await act(finish);
  assert.match(document.querySelector('dialog').textContent, /second.pdf/);
  assert.doesNotMatch(text(), /LATE FIRST DOCUMENT/);
  assert.equal(field('Supporting evidence').value, 'Keep the second document draft');
});

test('Escape and browser unload preserve corrections until the user discards them', async () => {
  await documents();
  await review();
  await change('Supporting evidence', 'Do not lose this correction');
  await act(async () =>
    document.querySelector('dialog').dispatchEvent(new window.Event('cancel', { cancelable: true }))
  );
  assert.equal(field('Supporting evidence').value, 'Do not lose this correction');
  const unloading = new window.Event('beforeunload', { cancelable: true });
  window.dispatchEvent(unloading);
  assert.equal(unloading.defaultPrevented, true);
  window.confirm = () => true;
  await dialogClick('Cancel');
  assert.equal(document.querySelector('dialog'), null);
  const after = new window.Event('beforeunload', { cancelable: true });
  window.dispatchEvent(after);
  assert.equal(after.defaultPrevented, false);
});

for (const [status, code] of [
  [409, 'EXTRACTION_NOT_READY'],
  [422, 'EXTRACTION_FAILED'],
  [404, 'NOT_FOUND'],
]) {
  test(`a ${code} import failure removes stale editable suggestions and offers recovery`, async () => {
    await documents();
    await review();
    await checkbox('I understand that importing replaces');
    state.intercept = (path) =>
      path.endsWith('/apply')
        ? json({ error: { code, message: 'The document is no longer ready for import.' } }, status)
        : null;
    await dialogClick('Apply reviewed sections');
    assert.equal(document.querySelector('dialog form'), null);
    assert.ok(dialogButton('Continue with manual entry'));
    assert.equal(state.requests.filter((r) => r.path.endsWith('/apply')).length, 1);
  });
}

test('changing accounts while extraction loads discards a late private document response', async () => {
  await documents();
  let finish;
  state.intercept = async (path) => {
    if (!path.endsWith('/extraction')) return null;
    const result = await state.server.dispatch('GET', path);
    result.suggestedSections.skills[0].evidenceText = 'PREVIOUS ACCOUNT PRIVATE TEXT';
    return new Promise((resolve) => {
      finish = () => resolve(json(result));
    });
  };
  await review();
  await state.server.dispatch('POST', '/auth/login', {
    email: 'new@example.test',
    password: 'Demo1234!',
  });
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  assert.equal(document.querySelector('dialog'), null);
  await act(finish);
  assert.doesNotMatch(text(), /PREVIOUS ACCOUNT PRIVATE TEXT/);
  assert.equal(field('Display name').value, '');
});
