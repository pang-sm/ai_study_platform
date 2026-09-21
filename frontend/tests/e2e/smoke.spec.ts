import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// The product now requires a session for every learning surface, so the ungated smoke checks
// cover what can be verified without one: the sign-in screens, the shell-free layout they use,
// and the honest failure the app shows when the API cannot answer. The authenticated surfaces
// are covered by `p7a-auth-surfaces.spec.ts` and the backend-gated VQA specs.

test('sign-in page renders cleanly with no console errors', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error' && !msg.text().includes('401 (Unauthorized)')) {
      consoleErrors.push(msg.text());
    }
  });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  await page.goto('/login');

  await expect(page.getByRole('heading', { name: '登录', level: 1 })).toBeVisible();
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test('the sign-in screens render without the product shell', async ({ page }) => {
  await page.goto('/login');

  // No learning-space navigation on a screen the visitor cannot use yet.
  await expect(page.getByRole('navigation', { name: '主导航' })).toHaveCount(0);
  await expect(page.getByRole('contentinfo')).toBeVisible();
});

test('desktop viewport has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/login');
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test('mobile viewport has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/login');
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test('a protected route never renders without a session', async ({ page }) => {
  await page.goto('/exam/cs408');

  // Without a reachable session probe the honest outcome is a reported failure with a retry —
  // never a learning surface rendered for an unidentified visitor.
  await expect(page.getByRole('heading', { name: '学习工作区' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
});
