// Opt-in acceptance pass for the converged shell and the learning surfaces it frames.
//
// WHY IT IS OPT-IN
// ----------------
// This is the only place the real breakpoint behaviour can be checked: jsdom applies no media
// queries, so the header-row / panel switch and the phone layouts are invisible to the unit
// suite. It needs the authenticated E2E harness, which `npm run test:e2e` does not start, so
// it skips unless all three of these are true:
//
//   1. the harness is up:            bash scripts/start-e2e-backend.sh --json
//   2. a FRESH dev server points at it:
//      VITE_API_BASE_URL=<base_url> npm run dev
//      (a long-running dev server keeps a stale router module graph and answers for code that is
//      no longer on disk — restart it rather than reusing it)
//   3. the run is marked:
//      P7B_E2E=1 P7B_API_BASE=<base_url> npx playwright test tests/e2e/p7b-acceptance.spec.ts
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const API = process.env.P7B_API_BASE ?? '';
const ENABLED = process.env.P7B_E2E === '1' && API !== '';

const USERNAME = 'e2e_learner';
const PASSWORD = 'e2e-learner-pass-1';

/** The five destinations a phone moves between, and the widths the layouts are accepted at. */
const WIDTHS = [
  { width: 1440, height: 900 },
  { width: 1366, height: 768 },
  { width: 1024, height: 800 },
  { width: 834, height: 1112 },
  { width: 390, height: 844 },
];

const SURFACES = [
  { path: '/', name: 'home' },
  { path: '/profile', name: 'profile' },
  { path: '/programming/python/projects/1', name: 'workbench' },
];

/**
 * Signing in has to be *waited for*: the sign-in screen already has an `h1`, so asserting one
 * proves nothing and would navigate away while the session request is still in flight.
 */
async function signIn(page: Page) {
  await page.goto('/login');
  await page.getByLabel('账号或邮箱').fill(USERNAME);
  // `exact` matters: the password panel is announced as 「密码登录」 and Playwright's label
  // matching is substring-based, so the loose form would also resolve to the panel.
  await page.getByLabel('密码', { exact: true }).fill(PASSWORD);
  await page.getByRole('button', { name: '登录' }).click();
  await expect(page.getByRole('navigation', { name: '主导航', exact: true })).toBeVisible({
    timeout: 20_000,
  });
}

const headerNav = (page: Page) => page.getByRole('navigation', { name: '主导航', exact: true });
const drawer = (page: Page) => page.getByRole('navigation', { name: '主导航（移动）', exact: true });
/** Every destination the header row carries on a wide screen. */
const DESTINATIONS = ['/', '/exam', '/course', '/programming', '/review', '/reports', '/membership'];

test.describe('P7-B responsive and accessibility acceptance', () => {
  test.skip(
    !ENABLED,
    'needs the E2E harness and a fresh dev server — see the header of this file',
  );

  test('the shell keeps one row of destinations and folds it into the panel below the wide breakpoint', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);

    for (const size of WIDTHS) {
      await page.setViewportSize(size);
      await page.goto('/');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

      const wide = size.width >= 1024;

      if (wide) {
        await expect(headerNav(page), `${size.width}px header row`).toBeVisible();
        await expect(page.getByRole('button', { name: '打开导航菜单' })).toBeHidden();
      } else {
        await expect(headerNav(page), `${size.width}px header row`).toBeHidden();

        // The panel is a real destination list, not a decorative disclosure.
        await page.getByRole('button', { name: '打开导航菜单' }).click();
        await expect(drawer(page)).toBeVisible();
        await expect(drawer(page).getByRole('link', { name: '编程学习' })).toBeVisible();
        await page.keyboard.press('Escape');
        await expect(drawer(page)).toBeHidden();
      }

      // No permanent column and no bottom bar at any width: the navigation is the header's.
      await expect(
        page.getByRole('navigation', { name: '学习空间导航' }),
        `${size.width}px side column`,
      ).toHaveCount(0);
      await expect(
        page.getByRole('navigation', { name: '主导航（底部）' }),
        `${size.width}px bottom bar`,
      ).toHaveCount(0);
    }
  });

  test('the panel carries the same destinations the header row does', async ({ page }) => {
    await signIn(page);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');

    await page.getByRole('button', { name: '打开导航菜单' }).click();
    const hrefs = await drawer(page)
      .getByRole('link')
      .evaluateAll((links) => links.map((link) => link.getAttribute('href')));
    expect(hrefs).toEqual(DESTINATIONS);
  });

  test('every surface lays out without horizontal overflow and is captured', async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    for (const surface of SURFACES) {
      for (const size of WIDTHS) {
        await page.setViewportSize(size);
        await page.goto(surface.path);
        // Authenticated, and the route rendered rather than redirecting to sign-in.
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });
        await expect(page).not.toHaveURL(/\/login/);

        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow, `${surface.name} at ${size.width}px`).toBeLessThanOrEqual(1);

        await page.screenshot({
          path: `test-results/p7b/${surface.name}-${size.width}.png`,
          fullPage: true,
        });
      }
    }
  });

  test('the home focus slot leads the page, above the agenda, at both ends of the range', async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);

    // The harness learner still needs onboarding, so the focus slot first holds the setup prompt.
    // Completing the settings through their real endpoints is what puts the server's ranked action
    // in that slot instead; `needs_onboarding` is only cleared by the onboarding endpoint, so both
    // calls are needed. Which variant rendered is recorded as an annotation.
    await page.request.put(`${API}/me/profile`, {
      data: { learning_direction: '计算机考研 408', focus_courses: '数据结构、操作系统' },
    });
    const onboarded = await page.request.post(`${API}/programming/onboarding`, {
      data: {
        main_language: 'Python',
        selected_languages: ['Python'],
        level: 'basic',
        problems: [],
        onboarding_completed: true,
      },
    });
    expect(onboarded.ok()).toBe(true);

    for (const size of [WIDTHS[0]!, WIDTHS[4]!]) {
      await page.setViewportSize(size);
      await page.goto('/');

      const ranked = page.getByText('现在先做', { exact: true });
      const setup = page.getByText('先设置一个学习方向', { exact: true });
      await expect(ranked.or(setup).first()).toBeVisible({ timeout: 20_000 });
      const variant = (await ranked.count()) ? 'ranked' : 'setup';
      test
        .info()
        .annotations.push({ type: 'focus-slot', description: `${size.width}px: ${variant}` });

      const focus = (await ranked.or(setup).first().boundingBox())!;
      const spaces = (await page.getByRole('heading', { name: '我的学习方向' }).boundingBox())!;

      expect(focus.y, `${size.width}px: the decision above the directions`).toBeLessThan(spaces.y);

      // The rest of today's work sits between them — when there IS any. An agenda with one entry
      // promotes that entry and has no list, which is a real state and not a missing section.
      const restOfToday = page.getByRole('heading', { name: '今天接下来' });
      if (await restOfToday.isVisible().catch(() => false)) {
        const next = (await restOfToday.boundingBox())!;
        expect(focus.y, `${size.width}px: the decision above the rest of today`).toBeLessThan(next.y);
        expect(next.y, `${size.width}px: today's work above the directions`).toBeLessThan(spaces.y);
      }

      // The page used to also close with the eight most recent learning events, a second index of
      // the three spaces, and the tier standing. All three restated what the header, 学习报告 and
      // the membership page already hold, so the regression this guards is any of them creeping
      // back in — and the log is the one that pushed today's work off the screen.
      await expect(page.getByRole('heading', { name: '最近学习' })).toHaveCount(0);
      await expect(page.getByRole('heading', { name: '去别的学习方向' })).toHaveCount(0);
      await expect(page.getByRole('heading', { name: '会员档位与可用额度' })).toHaveCount(0);

      // Nothing may scroll sideways at a width the product is actually read at.
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${size.width}px: home must not scroll sideways`).toBeLessThanOrEqual(0);

      await page.screenshot({
        path: `test-results/p7b/home-${variant}-${size.width}.png`,
        fullPage: true,
      });
    }
  });

  test('the workbench separates the three tool tiers visually', async ({ page }) => {
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/programming/python/projects/1');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });

    const deterministic = page.getByRole('group', { name: '确定性工具（不调用模型、不消耗额度）' });
    const ai = page.getByRole('region', { name: 'AI Debug（AI 代码分析）' });
    await expect(deterministic).toBeVisible();
    await expect(ai).toBeVisible();

    const det = (await deterministic.boundingBox())!;
    const aiBox = (await ai.boundingBox())!;
    expect(det.y, 'deterministic tier above the AI tier').toBeLessThan(aiBox.y);

    // The agent workflow is the widest and rarest one, so it starts folded.
    const agentSummary = page.getByText(/高级工作流：Debug Agent/);
    await expect(agentSummary).toBeVisible();
    await expect(page.locator('details', { has: agentSummary })).not.toHaveAttribute('open', '');

    await page.screenshot({ path: 'test-results/p7b/workbench-tiers-1440.png', fullPage: true });
  });

  test('axe reports no violations on the converged surfaces', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    // Each surface is awaited before it is analysed: `goto` resolves on load, and a React route
    // that has not mounted yet is an empty document — which axe quite correctly reports as
    // having no main landmark.
    await page.goto('/login');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

    await page.goto('/register');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

    await signIn(page);
    for (const path of ['/', '/profile', '/programming/python/projects/1']) {
      await page.goto(path);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });
      expect((await new AxeBuilder({ page }).analyze()).violations, `axe on ${path}`).toEqual([]);
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    expect((await new AxeBuilder({ page }).analyze()).violations, 'axe on / at 390px').toEqual([]);
  });
});
