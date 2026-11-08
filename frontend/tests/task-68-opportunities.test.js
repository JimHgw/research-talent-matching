import test from 'node:test';
import assert from 'node:assert/strict';
import {
  act,
  state,
  mount,
  click,
  change,
  field,
  button,
  text,
  json,
  fixture,
} from './support/app-harness.js';

async function owned(status = 'PUBLISHED', availabilityStatus = 'ACTIVE') {
  const item = { ...(await fixture('opportunity-published')), status, availabilityStatus };
  if (availabilityStatus === 'EXPIRED') item.content.deadlineAt = '2000-01-01T00:00:00Z';
  state.intercept = (path) =>
    path.startsWith('/opportunities?scope=mine')
      ? json({ items: [item], page: 1, pageSize: 20, total: 1 })
      : path === `/opportunities/${item.id}`
        ? json(item)
        : null;
  await mount('team@example.test');
  await click('My opportunities');
  return item;
}

for (const mode of ['lost-response', 'invalid-success']) {
  test(`list publication ${mode} blocks repeated publish and reconciles through the existing editor`, async () => {
    const item = await owned('DRAFT', 'DRAFT');
    const previous = state.intercept;
    state.intercept = (path, options) => {
      if (path === `/opportunities/${item.id}/publish`) {
        item.status = 'PUBLISHED';
        item.availabilityStatus = 'ACTIVE';
        item.revision++;
        if (mode === 'lost-response') throw new TypeError('Lost publish response');
        return json({ id: item.id });
      }
      return previous(path, options);
    };
    await click('Publish');
    assert.equal(button('Publish').disabled, true);
    await click('Publish');
    assert.equal(state.requests.filter((r) => r.path.endsWith('/publish')).length, 1);
    await click('Reload latest data');
    assert.ok(document.querySelector('dialog'));
    assert.equal(button('Save opportunity').disabled, true);
    await act(async () =>
      [...document.querySelectorAll('dialog button')]
        .find((node) => node.textContent.trim() === 'Reload latest data')
        .click()
    );
    assert.match(text(), /Latest saved version/);
    await click('Use latest version');
    assert.equal(button('Save opportunity').disabled, true);
    assert.equal(state.requests.filter((r) => r.path.endsWith('/publish')).length, 1);
    assert.equal(item.status, 'PUBLISHED');
  });
}

test('another publication cannot overwrite an unresolved publication outcome', async () => {
  const first = await owned('DRAFT', 'DRAFT');
  const second = {
    ...structuredClone(first),
    id: 'second-draft',
    content: { ...first.content, title: 'Second draft' },
  };
  const previous = state.intercept;
  state.intercept = (path, options) => {
    if (path.startsWith('/opportunities?scope=mine'))
      return json({ items: [first, second], page: 1, pageSize: 20, total: 2 });
    if (path.endsWith('/publish')) throw new TypeError('Unknown publication outcome');
    return previous(path, options);
  };
  await act(async () => window.dispatchEvent(new window.Event('focus')));
  await click('Publish');
  const actions = [...document.querySelectorAll('.team-opportunity button')].filter(
    (node) => node.textContent.trim() === 'Publish'
  );
  assert.equal(actions.length, 2);
  assert.equal(
    actions.every((node) => node.disabled),
    true
  );
  await act(async () => actions[1].click());
  assert.equal(state.requests.filter((r) => r.path.endsWith('/publish')).length, 1);
});

test('pending list publication submits its saved revision once and disables repeated clicks', async () => {
  const item = await owned('DRAFT', 'DRAFT');
  const revision = item.revision,
    previous = state.intercept;
  let release;
  state.intercept = (path, options) =>
    path.endsWith('/publish')
      ? new Promise((resolve) => {
          release = () => {
            Object.assign(item, {
              status: 'PUBLISHED',
              availabilityStatus: 'ACTIVE',
              revision: revision + 1,
            });
            resolve(json(item));
          };
        })
      : previous(path, options);
  const publish = button('Publish');
  await act(async () => publish.click());
  assert.equal(publish.disabled, true);
  await act(async () => publish.click());
  const attempts = state.requests.filter((r) => r.path.endsWith('/publish'));
  assert.equal(attempts.length, 1);
  assert.equal(attempts[0].body.expectedRevision, revision);
  await act(async () => release());
  assert.match(document.querySelector('.team-opportunity').textContent, /PUBLISHED/);
});

test('a lost reopen response keeps the expired snapshot until explicit comparison accepts the server result', async () => {
  const item = await owned('PUBLISHED', 'EXPIRED');
  await click('Edit');
  const previous = state.intercept;
  state.intercept = (path, options, body) => {
    if (path === `/opportunities/${item.id}` && options.method === 'PUT') {
      item.content = body.content;
      item.revision++;
      item.availabilityStatus = 'ACTIVE';
      throw new TypeError('Reopen committed but response lost');
    }
    return previous(path, options, body);
  };
  await change('Deadline', '2099-01-01T12:00');
  await click('Save and reopen opportunity');
  assert.equal(button('Save and reopen opportunity').disabled, true);
  assert.equal(field('Deadline').value, '2099-01-01T12:00');
  await click('Reload latest data');
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
  await click('Use latest version');
  assert.equal(text().includes('Reopen opportunity'), false);
  assert.equal(state.requests.find((r) => r.method === 'PUT').body.reopen, true);
});

test('a pending reopen freezes input and repeated clicks issue only the reviewed revision once', async () => {
  const item = await owned('PUBLISHED', 'EXPIRED');
  await click('Edit');
  const revision = item.revision,
    previous = state.intercept;
  let release;
  state.intercept = (path, options, body) =>
    path === `/opportunities/${item.id}` && options.method === 'PUT'
      ? new Promise((resolve) => {
          release = () =>
            resolve(
              json({
                ...item,
                content: body.content,
                revision: revision + 1,
                availabilityStatus: 'ACTIVE',
              })
            );
        })
      : previous(path, options, body);
  await change('Deadline', '2099-01-01T12:00');
  await click('Save and reopen opportunity');
  await click('Save and reopen opportunity');
  assert.equal(field('Deadline').matches(':disabled'), true);
  assert.equal(state.requests.filter((r) => r.method === 'PUT').length, 1);
  assert.equal(state.requests.find((r) => r.method === 'PUT').body.expectedRevision, revision);
  await act(async () => release());
  assert.equal(!!document.querySelector('dialog'), false);
});

test('an ordinary save cannot claim an expired opportunity reopened from an inconsistent response', async () => {
  const item = await owned('PUBLISHED', 'EXPIRED');
  await click('Edit');
  const previous = state.intercept;
  state.intercept = (path, options, body) =>
    path === `/opportunities/${item.id}` && options.method === 'PUT'
      ? json({
          ...item,
          revision: item.revision + 1,
          content: body.content,
          availabilityStatus: 'ACTIVE',
        })
      : previous(path, options, body);
  await change('Deadline', '2099-01-01T12:00');
  await click('Save opportunity');
  assert.equal(button('Save and reopen opportunity').disabled, true);
  assert.equal(button('Save opportunity').disabled, true);
  assert.match(text(), /request may have succeeded/);
  assert.doesNotMatch(text(), /Opportunity reopened\./);
});

test('a response belonging to a different opportunity cannot replace the draft or close the editor', async () => {
  const item = await owned();
  await click('Edit');
  const previous = state.intercept;
  state.intercept = (path, options, body) =>
    path === `/opportunities/${item.id}` && options.method === 'PUT'
      ? json({
          ...item,
          id: 'different-record',
          revision: item.revision + 1,
          content: body.content,
        })
      : previous(path, options, body);
  await change('Opportunity title *', 'Keep this opportunity draft');
  await click('Save opportunity');
  assert.equal(field('Opportunity title *').value, 'Keep this opportunity draft');
  assert.equal(button('Save opportunity').disabled, true);
  assert.match(text(), /request may have succeeded/);
});

for (const status of [403, 404]) {
  test(`opportunity comparison ${status} removes the inaccessible private form`, async () => {
    const item = await owned();
    await click('Edit');
    const previous = state.intercept;
    state.intercept = (path, options, body) =>
      path === `/opportunities/${item.id}`
        ? options.method === 'PUT'
          ? json({ error: { code: 'REVISION_CONFLICT', message: 'Changed elsewhere.' } }, 409)
          : json({ error: { code: 'NOT_FOUND', message: 'Opportunity unavailable.' } }, status)
        : previous(path, options, body);
    await change('Opportunity title *', 'Private draft before access loss');
    await click('Save opportunity');
    await click('Reload latest data');
    assert.equal(!!document.querySelector('.team-opportunity-fields'), false);
    assert.doesNotMatch(
      document.querySelector('dialog').textContent,
      /Private draft before access loss/
    );
  });
}
