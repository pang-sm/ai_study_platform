// The dev machine runs a local proxy (HTTP_PROXY/ALL_PROXY at 127.0.0.1:7890).
// Bypass it for loopback so the webServer/reuse detection and the browser connect
// directly to the dev server instead of being intercepted.
process.env.NO_PROXY = 'localhost,127.0.0.1';
process.env.no_proxy = 'localhost,127.0.0.1';

import { defineConfig, devices } from '@playwright/test';

// The default target is the local dev server. `PA_BASE_URL` points the run at an EXTERNAL
// acceptance server instead — the production bundle served behind a same-origin `/api` proxy —
// and Playwright then attaches to it rather than starting a dev server of its own. That is what
// allows an isolated run that does not depend on whatever happens to be listening on :5173.
const externalBase = process.env.PA_BASE_URL;
const localBase = 'http://127.0.0.1:5173';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: externalBase ?? localBase,
    trace: 'on-first-retry',
    launchOptions: {
      args: ['--no-proxy-server'],
    },
  },
  webServer: externalBase
    ? undefined
    : {
        command: 'npm run dev',
        url: localBase,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
