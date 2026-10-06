import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'vite';
import { readFileSync } from 'node:fs';

test('production build includes styles and excludes test helpers, fixtures and test dependencies', async () => {
  const result = await build({ logLevel: 'silent', build: { write: false, sourcemap: false } });
  const outputs = (Array.isArray(result) ? result : [result]).flatMap((r) => r.output);
  assert.ok(
    outputs.some((o) => o.type === 'asset' && o.fileName.endsWith('.css') && o.source.length > 1000)
  );
  const chunks = outputs.filter((o) => o.type === 'chunk');
  const scoped = JSON.parse(
    readFileSync(new URL('../package.json', import.meta.url), 'utf8')
  ).contributionTasks;
  for (const chunk of chunks) {
    for (const module of Object.keys(chunk.modules))
      assert.doesNotMatch(module, /\/tests\/|\/docs\/api\/examples\/|\/jsdom\//);
    if (scoped)
      for (const module of Object.keys(chunk.modules))
        assert.doesNotMatch(module, /\/features\/(matching|opportunities)\//);
    assert.doesNotMatch(
      chunk.code,
      /Demo1234!|talent@example\.test|createMockServer|banana-sprint1-demo-v1/
    );
  }
});
