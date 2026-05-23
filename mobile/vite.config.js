import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Plain SPA build. We use HashRouter so static hosts (Vercel, Netlify,
// any plain CDN) work without rewrite rules — every URL serves index.html
// and the hash determines the route.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    sourcemap: false,
    target: 'es2020',
  },
  server: {
    host: true,     // allow access from your phone on the LAN during dev
    port: 5173,
  },
});
