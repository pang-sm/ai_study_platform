// Opt-in acceptance pass for the three learning spaces (P7-C).
//
// Same gate as `p7b-acceptance.spec.ts`: the E2E harness must be up, a FRESH dev server must
// point at it, and the run must be marked. Without that the file skips, because none of the
// surfaces it checks can render without a session.
//
//   1. bash scripts/start-e2e-backend.sh --json
//   2. VITE_API_BASE_URL=<base_url> npm run dev      (fresh — never reuse a long-running server)
//   3. P7C_E2E=1 P7C_API_BASE=<base_url> P7C_COURSE_ID=<harness course_id> \
//        npx playwright test tests/e2e/p7c-spaces.spec.ts
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const API = process.env.P7C_API_BASE ?? '';
const ENABLED = process.env.P7C_E2E === '1' && API !== '';

const USERNAME = 'e2e_learner';
const PASSWORD = 'e2e-learner-pass-1';

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

/**
 * The course this learner is in is discovered from the app, not handed in: the harness prints a
 * contract in the console's own encoding, and the course list page is the real answer anyway.
 */
async function courseSurfaces(page: Page) {
  // The harness learner starts without a declared course, and an empty course list would leave
  // the course space untested. Declaring one through the profile's own endpoint is the real way
  // a course appears (`get_course_learning_selected_courses` falls back to `focus_courses`).
  await page.request.put(`${API}/me/profile`, {
    data: { learning_direction: '计算机考研 408', focus_courses: '数据结构、操作系统' },
  });

  await page.goto('/course');
  // The course list is the only thing linking into `/course/<id>`; the shell's own links are not.
  // `/course/setup?returnTo=…` also starts with `/course/` and appears in the index header, so it
  // has to be excluded by prefix — an exact `[href="/course/setup"]` would not match it. Only a
  // course row leads to a course.
  const link = page.locator('a[href^="/course/"]:not([href^="/course/setup"])').first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  const href = await link.getAttribute('href');
  if (!href) {
    test.skip(true, 'the harness learner has no course to open');
    return [];
  }
  return [
    { path: href, name: 'course-home', nav: '课程学习导航', activeTab: '概览' },
    { path: `${href}/materials`, name: 'course-materials', nav: '课程学习导航', activeTab: '资料' },
  ];
}

const FIXED_SURFACES = [
  { path: '/exam/cs408', name: 'exam-cs408', nav: 'CS408 工具导航', activeTab: '概览' },
  { path: '/programming', name: 'programming-home', nav: null, activeTab: null },
  { path: '/programming/python', name: 'programming-python', nav: '编程学习导航', activeTab: '练习' },
] as const;

test.describe('P7-C learning space acceptance', () => {
  test.skip(!ENABLED, 'needs the E2E harness and a fresh dev server — see the header of this file');

  test('each space names its own context, marks its tab and lays out on a phone', async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);

    const surfaces = [...(await courseSurfaces(page)), ...FIXED_SURFACES];

    for (const surface of surfaces) {
      for (const size of [
        { width: 1440, height: 900 },
        { width: 390, height: 844 },
      ]) {
        await page.setViewportSize(size);
        await page.goto(surface.path);
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });
        await expect(page).not.toHaveURL(/\/login/);

        if (surface.nav) {
          const nav = page.getByRole('navigation', { name: surface.nav });
          await expect(nav, `${surface.name} tabs at ${size.width}px`).toBeVisible();
          // The current tool is marked, and the strip is reachable without hovering.
          await expect(nav.getByRole('link', { name: surface.activeTab ?? '' })).toHaveAttribute(
            'aria-current',
            'page',
          );
          await expect(page.getByRole('navigation', { name: '面包屑' })).toBeVisible();
        }

        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow, `${surface.name} at ${size.width}px`).toBeLessThanOrEqual(1);

        await page.screenshot({
          path: `test-results/p7c/${surface.name}-${size.width}.png`,
          fullPage: true,
        });
      }
    }
  });

  test('axe reports no violations on the converged spaces', async ({ page }) => {
    test.setTimeout(300_000);
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    for (const surface of [...(await courseSurfaces(page)), ...FIXED_SURFACES]) {
      await page.goto(surface.path);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });
      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations, `axe on ${surface.name}`).toEqual([]);
    }
  });

  test('the reading surface never leads with a payload', async ({ page }) => {
    await signIn(page);
    await page.setViewportSize({ width: 1440, height: 900 });

    for (const surface of [...(await courseSurfaces(page)), ...FIXED_SURFACES]) {
      await page.goto(surface.path);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });

      // Any element holding a JSON-looking fragment must sit inside a folded disclosure.
      const leaks = await page.evaluate(() => {
        const out: string[] = [];
        for (const element of Array.from(document.querySelectorAll('body *'))) {
          if (element.children.length > 0) continue;
          const text = element.textContent ?? '';
          if (!/\{"|"\s*:\s*"/.test(text)) continue;
          if (!element.closest('details')) out.push(text.slice(0, 60));
        }
        return out;
      });
      expect(leaks, `${surface.name} shows a payload in its reading surface`).toEqual([]);
    }
  });
});
