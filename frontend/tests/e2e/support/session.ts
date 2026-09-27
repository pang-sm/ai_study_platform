// The canonical authenticated session for Playwright specs.
//
// WHY THIS EXISTS
// A handful of specs were written before every learning surface required a session. They stubbed
// one or two endpoints, navigated straight to a protected route, and asserted content — which
// cannot work now: the root guard reads the session first and sends a signed-out visitor to
// /login, so those assertions could never pass, and they were "did not run" often enough that
// nobody noticed. They are migrated here rather than deleted, and rather than being left skipped.
//
// WHAT IT DOES NOT DO
// It does not weaken the guard, and it does not stub the session: signing in goes through the
// real /login endpoint of the isolated acceptance harness, exactly as p7b-acceptance does.
import { expect, type Page } from '@playwright/test';

/** The isolated harness, when one is running. Same contract as `scripts/start-e2e-backend.sh`. */
export const HARNESS = {
  enabled: process.env.P7B_E2E === '1' && Boolean(process.env.P7B_API_BASE),
  apiBase: process.env.P7B_API_BASE ?? '',
  username: 'e2e_learner',
  password: 'e2e-learner-pass-1',
};

/** Skipped — loudly — when no harness is up, instead of failing on a redirect it cannot pass. */
export const requiresHarness = HARNESS.enabled
  ? []
  : ['needs the authenticated harness: bash scripts/start-e2e-backend.sh --json, then P7B_E2E=1 P7B_API_BASE=<base_url>'];

export async function signIn(page: Page): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('账号或邮箱').fill(HARNESS.username);
  // `exact` matters: the password panel is announced as 「密码登录」 and Playwright's label
  // matching is substring-based, so the loose form would also resolve to the panel.
  await page.getByLabel('密码', { exact: true }).fill(HARNESS.password);
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page.getByRole('navigation', { name: '主导航', exact: true })).toBeVisible({
    timeout: 20_000,
  });
}
