import { readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
const tasks = process.argv.slice(2).filter((value) => value !== '--');
if (
  tasks.some(
    (value) =>
      !['18', '19', '20', '21', '22', '41', '47', '49', '53', '61', '67', '68', 'i18n'].includes(
        value
      )
  )
)
  throw new Error(
    'Choose task 18, 19, 20, 21, 22, 41, 47, 49, 53, 61, 67, 68 or i18n; omit tasks to run all checks.'
  );
const files = readdirSync(new URL('../tests/', import.meta.url))
  .filter(
    (name) =>
      name.endsWith('.test.js') &&
      (!tasks.length ||
        tasks.some((task) => name.startsWith(task === 'i18n' ? 'i18n-' : `task-${task}-`)))
  )
  .sort()
  .map((name) => `tests/${name}`);
if (!files.length) throw new Error('No test cases found. A zero-test run is not a passing check.');
const result = spawnSync(
  process.execPath,
  ['--import', './tests/setup-jsx.js', '--test', '--test-reporter=spec', ...files],
  { stdio: 'inherit', cwd: new URL('../', import.meta.url) }
);
if (result.error) throw result.error;
process.exit(result.status ?? 1);
