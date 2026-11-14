import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In docker-compose the backend is reachable as http://backend:5000, locally as localhost.
const apiTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:5000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // Bind-mounted sources on Windows/macOS Docker don't emit fs events reliably.
    watch:
      process.env.VITE_USE_POLLING === 'true'
        ? { usePolling: true, interval: 1000, ignored: ['**/node_modules/**', '**/dist/**'] }
        : undefined,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
    restoreMocks: true,
  },
});
