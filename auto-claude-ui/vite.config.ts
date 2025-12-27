import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

/**
 * Vite configuration for browser mode (non-Electron).
 *
 * This config is used when running `vite` directly for browser development mode.
 * For Electron mode, see electron.vite.config.ts
 */
export default defineConfig({
  root: resolve(__dirname, 'src/renderer'),
  plugins: [react()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src/renderer'),
      '@shared': resolve(__dirname, 'src/shared')
    }
  },
  server: {
    port: 5173,
    watch: {
      ignored: [
        '**/node_modules/**',
        '**/.git/**',
        '**/.worktrees/**',
        '**/.auto-claude/**',
        '**/out/**',
        resolve(__dirname, '../.worktrees/**'),
        resolve(__dirname, '../.auto-claude/**'),
      ]
    }
  },
  build: {
    outDir: resolve(__dirname, 'out/renderer'),
    rollupOptions: {
      input: {
        index: resolve(__dirname, 'src/renderer/index.html')
      }
    }
  }
});
