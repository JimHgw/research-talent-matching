import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    server: {
      port: 5173,
      proxy: {
        '/api': { target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false },
      },
    },
    build: {
      sourcemap: true,
      rollupOptions: {
        output: {
          // Cache dictionaries independently while keeping language changes synchronous.
          manualChunks(id) {
            const locale = id.match(/\/shared\/locales\/(?:workspace\/)?([\w-]+)\.js$/)?.[1];
            if (locale && locale !== 'index') return `locale-${locale}`;
          },
        },
      },
    },
  };
});
