import test from 'node:test';
import assert from 'node:assert/strict';
import { copyFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

// Exercise the actual runner in a disposable checkout, without recursively
// starting this suite or needing dependencies in the fixture project.
function runFixture(source, args = []) {
  const directory = mkdtempSync(join(tmpdir(), 'frontend runner '));
  try {
    const root = join(directory, 'checkout with spaces');
    mkdirSync(join(root, 'scripts'), { recursive: true });
    mkdirSync(join(root, 'tests'));
    writeFileSync(join(root, 'package.json'), '{"type":"module"}');
    copyFileSync(new URL('../scripts/test.js', import.meta.url), join(root, 'scripts/test.js'));
    writeFileSync(join(root, 'tests/setup-jsx.js'), '');
    writeFileSync(join(root, 'tests/task-18-probe.test.js'), source);
    const env = { ...process.env };
    // A fresh terminal does not inherit the parent node:test worker marker.
    delete env.NODE_TEST_CONTEXT;
    const result = spawnSync(process.execPath, [join(root, 'scripts/test.js'), ...args], {
      cwd: directory,
      env,
      encoding: 'utf8',
      timeout: 15000,
    });
    assert.ifError(result.error);
    return { status: result.status, output: result.stdout + result.stderr };
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

test('local runner discovers tests from another directory and handles spaces in paths', () => {
  const result = runFixture(
    "import test from 'node:test'; test('portable runner probe', () => {});",
    ['18']
  );
  assert.equal(result.status, 0, result.output);
  assert.match(result.output, /portable runner probe/);
  assert.match(result.output, /tests 1/);
});

test('local runner propagates a failing test instead of reporting success', () => {
  const result = runFixture(
    "import test from 'node:test'; test('failing probe', () => { throw new Error('expected failure'); });"
  );
  assert.equal(result.status, 1, result.output);
  assert.match(result.output, /expected failure/);
});

test('local runner rejects a task without tests instead of silently running zero tests', () => {
  const result = runFixture('', ['22']);
  assert.equal(result.status, 1, result.output);
  assert.match(result.output, /No test cases found/);
});
