import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const port = Number(env.FRONTEND_PORT || 3000);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('FRONTEND_PORT must be an integer from 1 to 65535.');
  }
  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1', port, strictPort: true,
      proxy: { '/api': { target: env.FLASK_API_PROXY_TARGET || 'http://127.0.0.1:5000', changeOrigin: true } },
    },
  };
});
