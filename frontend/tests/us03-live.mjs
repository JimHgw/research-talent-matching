import assert from 'node:assert/strict';
import {
  mount,
  remount,
  cleanup,
  until,
  text,
  change,
  click,
  login,
  checkbox,
  button,
  requests,
} from './support/live-app.js';
import { createApi } from '../src/api/client.js';
import { equal } from 'node:assert';
import { waitForDebugger } from 'node:inspector';

const reviewLabel =
  'I have reviewed my saved profile and confirm it reflects my information.';

try {
    // 1. Log in through the real React login page.
    await mount();
    await login('talent@example.test');
    await until(() => text().includes('Tell your research story'));

    assert.equal(button('Confirm profile').disabled, true);

    // 2. Enter valid content through the profile editor.
    await change('Display name', 'US-03 integration talent');
    await click('Add education');
    await change('Institution *', 'UNSW');
    await change('Qualification *', 'Bachlor of IT');
    assert.equal(button('Confirm profile').disabled, true);

    await click('Save changes');
    await until(
    () =>
      text().includes('Needs confirmation') &&
      button('Save changes')?.disabled
    );
    const api = createApi();
    await api.session();

    const saved = await api.profile();

    // 3. Just saved but not comfirm
    assert.equal(saved.confirmation.status, 'UNCONFIRMED');
    assert.equal(button('Confirm profile').disabled, true);

    assert.equal(
        requests.filter(
            (requests) =>
                requests.method === 'POST' &&
                requests.url.endsWith('/me/profile/confirmation')
        ).length,
        0
    );

    // 4. Review and confirm through the page.
    await checkbox(reviewLabel);
    assert.equal(button('Confirm profile').disabled, false);

    await click('Confirm profile');
    await until(() => text().includes('This version is confirmed.'));

    // 5. Compare the confirmed version with saved version
    const confirmed = await api.profile();
    assert.equal(confirmed.confirmation.status, 'CONFIRMED');
    assert.equal(confirmed.revision, saved.revision);
    assert.equal(confirmed.confirmation.confirmedRevision, saved.revision);
    assert.ok(confirmed.confirmation.confirmedAt);
    assert.deepEqual(confirmed.content, saved.content);

    // 6. Check if there is change when confirm again
    const repeated = await api.confirm(confirmed.revision);
    assert.deepEqual(repeated, confirmed);

    // 7. Recreate the React
    await remount;
    await until(
        () =>
        text().includes('Tell your research story') &&
        text().includes('This version is confirmed.')
    );
    assert.deepEqual(await api.profile(), confirmed);

    // 8. Edit and save; the previous confirmation must be cleared
    await change('Display name', 'Updated US-03 talent');
    assert.equal(button('Confirm profile').disabled, true);

    await click('Save changes');
    await until(
        () =>
        text().includes('Needs confirmation') &&
        button('Save changes')?.disabled
    );
    const updated = await api.profile();
    assert.equal(updated.revision, confirmed.revision + 1);
    assert.equal(updated.content.displayName, 'Updated US-03 talent');
    assert.equal(updated.confirmation.status, 'UNCONFIRMED');
    assert.equal(updated.confirmation.confirmedRevision, null);
    assert.equal(updated.confirmation.confirmedAt, null);

    // 9. Confirm the new revision through the page.
    await checkbox(reviewLabel);
    await click('Confirm profile');
    await until(() => text().includes('This version is confirmed.'));

    const reconfirmed = await api.profile();
    assert.equal(reconfirmed.revision, updated.revision);
    assert.equal(reconfirmed.confirmation.status, 'CONFIRMED');
    assert.equal(
        reconfirmed.confirmation.confirmedRevision,
        updated.revision
    );
    assert.ok(reconfirmed.confirmation.confirmedAt);

    console.log('US-03 real HTTP integration passed');
} finally {
    await cleanup();
}