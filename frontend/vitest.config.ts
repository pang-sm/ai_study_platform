import path from 'node:path';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    restoreMocks: true,
    // Bound worker concurrency. Vitest's default here is one worker per test FILE — 22 on
    // this suite — and each jsdom worker spends ~2.4s on spawn + environment setup. On a
    // 12-CPU machine that oversubscription starves the 5s per-test budget: `npm run
    // test:run` timed out 1-3 tests per run, with the COUNT varying between identical runs
    // on an unchanged tree and never as an assertion failure. Every affected file passed
    // alone, together, and under any bounded pool. At 50% the suite is deterministic and no
    // slower (measured 11-17s vs ~18s).
    maxWorkers: '50%',
  },
});
