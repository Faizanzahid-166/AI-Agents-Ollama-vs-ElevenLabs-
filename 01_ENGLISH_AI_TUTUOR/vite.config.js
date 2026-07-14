// vite.config.js — ESM (root package.json has "type":"module")
import { defineConfig } from 'vite';
import react            from '@vitejs/plugin-react';
import { fileURLToPath } from 'url';
import path              from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  base: './',
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
