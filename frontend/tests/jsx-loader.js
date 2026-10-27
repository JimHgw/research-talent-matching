import { readFile } from 'node:fs/promises';
import { transformWithEsbuild } from 'vite';
export async function load(url, context, nextLoad) {
  // Match Vite's build-time flag for real HTTP source-link tests.
  if (url.endsWith('/features/opportunities/metadata.js')) {
    const source = await readFile(new URL(url), 'utf8');
    return {
      format: 'module',
      shortCircuit: true,
      source: source.replaceAll(
        'import.meta.env',
        JSON.stringify({ VITE_OPPORTUNITY_SOURCE_URLS: process.env.VITE_OPPORTUNITY_SOURCE_URLS })
      ),
    };
  }
  if (!url.endsWith('.jsx')) return nextLoad(url, context);
  const source = await readFile(new URL(url), 'utf8');
  const result = await transformWithEsbuild(source, url, { loader: 'jsx', jsx: 'transform' });
  return { format: 'module', source: result.code, shortCircuit: true };
}
