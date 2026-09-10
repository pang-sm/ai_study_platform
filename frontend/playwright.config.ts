// The dev machine runs a local proxy (HTTP_PROXY/ALL_PROXY at 127.0.0.1:7890).
// Bypass it for loopback so the webServer/reuse detection and the browser connect
// directly to the dev server instead of being intercepted.
process.env.NO_PROXY = 'localhost,127.0.0.1';
process.env.no_proxy = 'localhost,127.0.0.1';

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    launchOptions: {
      args: ['--no-proxy-server'],
    },
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:5173',
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
