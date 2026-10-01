// The course space's information architecture, in a real Chromium against a real backend.
//
// What the strip holds IS the IA, so the retirements are asserted as hard as the tabs. 概览 is
// gone — a first tab whose content described the other tabs is not a surface. 学习 is gone —
// reading a knowledge point is what opening one from 知识结构 does, so the workspace is reached
// from there and owns no tab. 学习状态 is gone — 记录 already states the course's own figures. A
// retired tab that quietly comes back is exactly how a converged IA drifts, which is why the
// absences are checked by name rather than left to the positive list.
//
// Same gate as `p7c-spaces.spec.ts`: without the harness the file skips loudly instead of failing
// on a redirect it could never pass.
//
//   1. bash scripts/start-e2e-backend.sh --json
//   2. VITE_API_BASE_URL=<base_url> npm run dev      (a FRESH server — never a long-running one)
//   3. P7B_E2E=1 P7B_API_BASE=<base_url> npx playwright test tests/e2e/course-workspace.spec.ts
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { HARNESS, requiresHarness, signIn } from './support/session';

test.skip(requiresHarness.length > 0, requiresHarness.join(' '));

/** The seven tabs, in the order a learner moves through them. */
const TABS = ['课程问答', '资料', '知识结构', '练习', '错题与复习', '计划', '记录'];

/** The tabs this product retired on purpose, and must not grow back. */
const RETIRED_TABS = ['概览', '学习', '学习状态'];

/** The course the run is about. It is declared, then read back off the page that lists it. */
const COURSE_NAME = '数据结构';

/**
 * The course this learner is in, discovered from the app rather than handed in.
 *
 * The harness learner starts with no declared course, and an empty course list would leave the
 * whole space untested. Declaring one through the profile's own endpoint is the real way a course
 * appears (`get_course_learning_selected_courses` falls back to `focus_courses`), and the index
 * is then the authority on its id.
 */
async function openCourse(page: Page): Promise<string> {
  await page.request.put(`${HARNESS.apiBase}/me/profile`, {
    data: { learning_direction: '计算机考研 408', focus_courses: COURSE_NAME },
  });
  await page.goto('/course');
  // `/course/setup?returnTo=…` also starts with `/course/` and sits in the index header, so it
  // has to be excluded by prefix — only a course row leads into a course.
  const link = page.locator('a[href^="/course/"]:not([href^="/course/setup"])').first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  return (await link.getAttribute('href')) ?? '';
}

test('the course strip holds the seven tabs, and none of the retired ones', async ({ page }) => {
  await signIn(page);
  const course = await openCourse(page);
  test.skip(!course, 'the harness learner has no course to open');

  await page.goto(`${course}/materials`);
  const nav = page.getByRole('navigation', { name: '专业学习导航' });
  await expect(nav).toBeVisible({ timeout: 20_000 });

  const labels = (await nav.getByRole('link').allInnerTexts()).map((text) => text.trim());
  expect(labels).toEqual(TABS);
  for (const retired of RETIRED_TABS) {
    await expect(nav.getByRole('link', { name: retired, exact: true })).toHaveCount(0);
  }
});

test('the study workspace owns one point and holds no list of them', async ({ page }) => {
  await signIn(page);
  const course = await openCourse(page);
  test.skip(!course, 'the harness learner has no course to open');

  // Opened by URL on purpose. The workspace is a page in its own right, so what it must NOT
  // contain is assertable whether or not this course has a structure yet — and that is the whole
  // claim: 知识结构 is the only door, so there is no second list here and no phone-sized picker
  // standing in for one.
  await page.goto(`${course}/study`);
  await expect(page.getByRole('heading', { level: 1, name: '学习' })).toBeVisible({ timeout: 20_000 });

  await expect(page.getByRole('navigation', { name: '知识点' })).toHaveCount(0);
  await expect(page.locator('#study-point-picker')).toHaveCount(0);
  await expect(page.getByRole('link', { name: '返回知识结构' })).toHaveAttribute(
    'href',
    `${course}/knowledge`,
  );
});

test('a knowledge point in 知识结构 opens the study workspace', async ({ page }) => {
  await signIn(page);
  const course = await openCourse(page);
  test.skip(!course, 'the harness learner has no course to open');

  await page.goto(`${course}/knowledge`);
  const point = page.locator(`a[href^="${course}/study?knowledge_point_id="]`).first();
  if ((await point.count()) === 0) {
    // Skipped, not asserted: the harness's scripted provider does not return a usable knowledge
    // structure (generation answers 502), so a course with no point to open is this fixture's
    // normal state — and the claim under test is one that cannot be built without a point.
    test.skip(true, 'this course has no active knowledge structure to open a point from');
  }

  const title = (await point.innerText()).trim();
  await point.click();
  await page.waitForURL(/\/study\?knowledge_point_id=\d+/);
  // The router moves the URL before React commits the destination, so the assertions hang on the
  // workspace's OWN landmark rather than on the address bar alone.
  await expect(page.locator('#study-point-title')).toHaveText(title);
  await expect(page.getByRole('link', { name: '返回知识结构' })).toBeVisible();
});

test('推荐练习 sits after the practice page heading, never before it', async ({ page }) => {
  await signIn(page);
  const course = await openCourse(page);
  test.skip(!course, 'the harness learner has no course to open');

  await page.goto(`${course}/practice`);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 20_000 });

  // Document order is what a reader gets, and it is asserted as order rather than as text: the
  // recommendation is an addition to the page, so it follows the page's own heading. Both states
  // of the region are matched — the loaded one is labelled by its own heading, the loading and
  // failed ones carry an aria-label — so the check does not depend on data arriving.
  const order = await page.evaluate(() => {
    const heading = document.querySelector('h1');
    const recommendations = document.querySelector(
      '#adaptive-practice-title, section[aria-label="推荐练习"]',
    );
    if (!heading || !recommendations) return null;
    return {
      heading: (heading.textContent ?? '').trim(),
      follows: (heading.compareDocumentPosition(recommendations) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0,
    };
  });
  expect(order, 'the practice page rendered no heading and no recommendations region').not.toBeNull();
  expect(order!.follows, `推荐练习 is rendered above the practice heading「${order!.heading}」`).toBe(true);
});

test('the course workspace keeps its context and has no axe violations on a phone', async ({ page }) => {
  await signIn(page);
  const course = await openCourse(page);
  test.skip(!course, 'the harness learner has no course to open');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${course}/knowledge`);
  const navigation = page.getByRole('navigation', { name: '专业学习导航' });
  await expect(navigation).toBeVisible({ timeout: 20_000 });
  await expect(navigation.getByRole('link', { name: '资料' })).toHaveAttribute(
    'href',
    `${course}/materials`,
  );

  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
