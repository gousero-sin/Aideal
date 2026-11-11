import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Bibliotecas grandes e estáveis ganham chunks próprios: o navegador mantém o
// cache delas entre deploys e os painéis lazy baixam só o próprio código.
const VENDOR_CHUNKS = [
  ['vendor-charts', ['/node_modules/recharts/', '/node_modules/d3-', '/node_modules/victory-vendor/',
    '/node_modules/internmap/', '/node_modules/decimal.js-light/', '/node_modules/es-toolkit/',
    '/node_modules/eventemitter3/', '/node_modules/@reduxjs/', '/node_modules/redux',
    '/node_modules/react-redux/', '/node_modules/immer/', '/node_modules/reselect/',
    '/node_modules/use-sync-external-store/', '/node_modules/tiny-invariant/', '/node_modules/clsx/']],
  ['vendor-motion', ['/node_modules/framer-motion/', '/node_modules/motion-dom/', '/node_modules/motion-utils/']],
  ['vendor-icons', ['/node_modules/lucide-react/']],
  ['vendor-react', ['/node_modules/react/', '/node_modules/react-dom/', '/node_modules/scheduler/']],
];

const vendorChunkFor = (id) => {
  const normalized = id.replace(/\\/g, '/');
  if (!normalized.includes('/node_modules/')) return undefined;
  const match = VENDOR_CHUNKS.find(([, needles]) => needles.some((needle) => normalized.includes(needle)));
  return match?.[0];
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: vendorChunkFor,
      },
    },
  },
});
