// Isolated browser test harness, never used by normal development or demonstrations.
import { createServer as createHttpServer } from 'node:http';
import { createServer as createViteServer } from 'vite';
import { createMockServer } from './support/server.js';
import { randomUUID } from 'node:crypto';
const sessions = new Map();
const backend = createHttpServer(async (req, res) => {
  try {
    let sessionId = req.headers.cookie?.match(/(?:^|; )test_session=([^;]+)/)?.[1];
    if (!sessionId || !sessions.has(sessionId)) {
      sessionId = randomUUID();
      sessions.set(sessionId, createMockServer());
      res.setHeader('Set-Cookie', `test_session=${sessionId}; HttpOnly; SameSite=Lax; Path=/`);
    }
    const chunks = [];
    let size = 0;
    for await (const chunk of req) {
      size += chunk.length;
      if (size > 11 * 1024 * 1024) {
        res.writeHead(413).end();
        return;
      }
      chunks.push(chunk);
    }
    let body;
    const bytes = Buffer.concat(chunks);
    if (bytes.length)
      body = req.headers['content-type']?.startsWith('multipart/form-data')
        ? await new Response(bytes, {
            headers: { 'Content-Type': req.headers['content-type'] },
          }).formData()
        : JSON.parse(bytes.toString());
    const value = await sessions
      .get(sessionId)
      .dispatch(req.method, req.url.replace(/^\/api\/v1/, ''), body);
    res.setHeader('Cache-Control', 'no-store');
    if (value === undefined) {
      res.writeHead(204).end();
      return;
    }
    if (value instanceof Blob) {
      res.setHeader('Content-Type', value.type);
      res.end(Buffer.from(await value.arrayBuffer()));
      return;
    }
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(value));
  } catch (error) {
    res.writeHead(error.status || 500, { 'Content-Type': 'application/json' });
    res.end(
      JSON.stringify({
        error: {
          code: error.code || 'TEST_ERROR',
          message: error.message,
          fieldErrors: error.fields || [],
          currentRevision: error.currentRevision,
        },
      })
    );
  }
});
await new Promise((resolve) => backend.listen(0, '127.0.0.1', resolve));
const vite = await createViteServer({
  define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/api/v1') },
  server: {
    host: '127.0.0.1',
    port: 5174,
    strictPort: true,
    proxy: { '/api': { target: `http://127.0.0.1:${backend.address().port}` } },
  },
});
await vite.listen();
console.log('UI TEST ONLY: http://127.0.0.1:5174 — synthetic responses, not the Python backend.');
console.log(
  'Test accounts: talent@example.test / team@example.test / new@example.test. Password: Demo1234!'
);
async function close() {
  await vite.close();
  backend.closeAllConnections();
  backend.close();
  process.exit(0);
}
process.on('SIGINT', close);
process.on('SIGTERM', close);
