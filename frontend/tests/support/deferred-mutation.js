import { state, json } from './app-harness.js';

export function deferMutation(matches) {
  let finish;
  state.intercept = (path, options, body) => {
    if (options.method === 'GET' || !matches(path)) return null;
    return new Promise((resolve) => {
      finish = async () => resolve(json(await state.server.dispatch(options.method, path, body)));
    });
  };
  return async () => {
    if (!finish) throw new Error('The expected mutation has not started.');
    await finish();
  };
}
