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
    // Run test FILES one at a time: the jsdom workers were starving each other's async budget.
    //
    // Vitest's default is one worker per test FILE — 22 here — and each jsdom worker spends
    // ~2.4s on spawn + environment setup. Under that contention `npm run test:run` timed out
    // 1-5 tests per run, with the COUNT and the failing SET both varying between identical runs
    // on an unchanged tree and never as an assertion failure: every failure is a Testing
    // Library `findBy*` timeout, the elements queried are rendered by the components, and every
    // affected file passes when run alone.
    //
    // Bounding the worker pool was enough while this suite ran in 11-17s (`maxWorkers: '50%'`
    // held then). It is ~140s now, with module transform and jsdom setup a large share of it, so
    // a bounded pool no longer helps: two consecutive runs at 50% failed 4 and 5 tests, and at
    // 25% still 1. Sequential execution removes the contention instead of capping it — the same
    // thing `--no-file-parallelism` does, which is the configuration that was measured clean.
    // Determinism is worth more than the throughput here, and no test's own timeout is changed.
    //
    // Verified at this setting: two consecutive full runs, both 71 files / 372 tests passed,
    // 0 failed (303s and 256s).
    fileParallelism: false,
  },
});
