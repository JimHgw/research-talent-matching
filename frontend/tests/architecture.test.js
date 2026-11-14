import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, existsSync } from 'node:fs';
import { dirname, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const src = fileURLToPath(new URL('../src/', import.meta.url));
const sourcePath = (file) => relative(src, file).replaceAll('\\', '/');
function files(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? files(resolve(dir, entry.name)) : [resolve(dir, entry.name)]
  );
}
const edges = files(src)
  .filter((file) => /\.(jsx?|tsx?|css)$/.test(file))
  .flatMap((file) => {
    const contents = readFileSync(file, 'utf8');
    const paths = [...contents.matchAll(/(?:from\s+|import\s+|@import\s+)["'](\.[^"']+)["']/g)].map(
      (match) => match[1]
    );
    return paths.map((path) => ({
      from: sourcePath(file),
      to: sourcePath(resolve(dirname(file), path)),
      resolved: resolve(dirname(file), path),
    }));
  });

test('every relative source import resolves to a file', () => {
  for (const edge of edges)
    assert.ok(existsSync(edge.resolved), `${edge.from} imports missing ${edge.to}`);
});

test('shared utilities and feature modules respect task boundaries', () => {
  for (const { from, to } of edges) {
    if (from.startsWith('shared/'))
      assert.ok(to.startsWith('shared/'), `Shared utility depends on a feature: ${from} -> ${to}`);
    if (from.startsWith('api/'))
      assert.ok(to.startsWith('api/'), `API depends on UI: ${from} -> ${to}`);
    if (from.startsWith('layout/'))
      assert.ok(
        !to.startsWith('features/') && !to.startsWith('app/'),
        `Shell must receive page configuration: ${from} -> ${to}`
      );
    if (from.startsWith('features/')) {
      const feature = from.split('/')[1];
      const permitted =
        to.startsWith(`features/${feature}/`) ||
        to.startsWith('api/') ||
        to.startsWith('shared/') ||
        (feature === 'documents' && to === 'features/profile/ProfileFields.jsx');
      assert.ok(permitted, `Unexpected feature dependency: ${from} -> ${to}`);
    }
  }
});
