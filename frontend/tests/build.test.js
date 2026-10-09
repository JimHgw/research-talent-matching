import test from 'node:test';
import assert from 'node:assert/strict';
import { build } from 'vite';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

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
    for (const [task, feature] of [
      ['H18ABANANA-19', 'opportunities'],
      ['H18ABANANA-20', 'matching'],
    ]) {
      if (scoped && !scoped.includes(task)) {
        for (const module of Object.keys(chunk.modules)) {
          assert.ok(!module.includes(`/features/${feature}/`), `Unexpected feature: ${feature}`);
        }
      }
    }
    assert.doesNotMatch(
      chunk.code,
      /Demo1234!|talent@example\.test|createMockServer|banana-sprint1-demo-v1/
    );
  }
  const modules = chunks.flatMap((chunk) => Object.keys(chunk.modules));
  for (const [task, feature] of [
    ['19', 'opportunities'],
    ['20', 'matching'],
  ]) {
    if (scoped?.includes(`H18ABANANA-${task}`))
      assert.ok(modules.some((name) => name.includes(`/features/${feature}/`)));
  }
});

test('the core page configuration builds without opportunity or matching feature dependencies', async () => {
  const result = await build({
    logLevel: 'silent',
    build: {
      write: false,
      sourcemap: false,
      lib: {
        entry: fileURLToPath(new URL('../src/app/core-workspace-config.jsx', import.meta.url)),
        formats: ['es'],
        fileName: 'core-workspace',
      },
      rollupOptions: { external: ['react', 'react-dom'] },
    },
  });
  for (const output of (Array.isArray(result) ? result : [result]).flatMap((r) => r.output)) {
    if (output.type !== 'chunk') continue;
    for (const module of Object.keys(output.modules))
      assert.doesNotMatch(module, /\/features\/(matching|opportunities)\//);
  }
});
