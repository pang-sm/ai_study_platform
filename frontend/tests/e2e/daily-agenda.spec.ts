// The home page in a real browser, with the session and the agenda stubbed so the run needs no
// backend. jsdom applies no media queries and no layout, so neither the phone layout nor a
// horizontal overflow is visible to the unit suite — both are only checkable here.
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const AGENDA = {
  policy_version: 'agenda_policy_v1',
  generated_at: '2026-09-25T00:00:00Z',
  items: [
    {
      action_type: 'review',
      service_namespace: 'exam_prep',
      domain_context: { exam_module_id: 'data_structure' },
      source_type: 'wrong_answer',
      source_id: 'r1',
      title: '错题 · 数据结构',
      summary: '累计做错 5 次，尚未订正',
      priority_reason: 'repeated_wrong',
      deep_link: '/exam/cs408/wrong?module=data_structure',
      due_at: null,
      facts: { wrong_count: 5, review_reason: 'wrong_answer_active' },
      status: 'needs_attention',
      resolved_by: 'review_completion',
    },
    {
      action_type: 'programming',
      service_namespace: 'programming',
      domain_context: { language: 'C', exercise_id: 11 },
      source_type: 'programming_exercise',
      source_id: '11',
      title: '设备序列号校验',
      summary: '标记为需要加强',
      priority_reason: 'needs_work',
      deep_link: '/programming/C/exercises/11',
      due_at: null,
      facts: { personal_status: 'needs_work' },
      status: 'needs_attention',
    },
    {
      action_type: 'programming',
      service_namespace: 'programming',
      domain_context: { language: 'Python', exercise_id: 13 },
      source_type: 'programming_exercise',
      source_id: '13',
      title: '设备序列号校验',
      summary: '标记为需要加强',
      priority_reason: 'needs_work',
      deep_link: '/programming/Python/exercises/13',
      due_at: null,
      facts: { personal_status: 'needs_work' },
      status: 'needs_attention',
    },
  ],
  total_items: 3,
  source_summary: {},
  semantics: 'facts',
};

async function stubHome(page: Page) {
  await page.route('**/me', (route) =>
    route.fulfill({
      json: { user: { id: 1, username: 'e2e_home', nickname: '验收学习者', plan: 'free', onboarding_completed: true } },
    }),
  );
  await page.route('**/course-learning/courses**', (route) => route.fulfill({ json: [] }));
  await page.route('**/exam/prep/profile', (route) =>
    route.fulfill({ json: { configured: true, exam_type: 'cs408', selected_subjects: [], subjects: [] } }),
  );
  await page.route('**/programming/onboarding', (route) =>
    route.fulfill({ json: { main_language: 'C', selected_languages: ['C'], onboarding_completed: true } }),
  );
  await page.route('**/learning/agenda**', (route) =>
    route.fulfill({ json: route.request().url().includes('/explain') ? {} : AGENDA }),
  );
}

test('Home states the one thing to do now, then the rest, then the three directions', async ({ page }) => {
  await stubHome(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');

  // The decision, with the backend's own deep link, and nothing folded underneath it.
  const decision = page.getByRole('region', { name: '现在先做' });
  await expect(decision).toBeVisible();
  await expect(decision.getByText('这道内容已经做错 5 次，建议优先完成订正。')).toBeVisible();
  await expect(decision.getByRole('link', { name: /继续学习/ })).toHaveAttribute(
    'href',
    '/exam/cs408/wrong?module=data_structure',
  );
  await expect(decision.locator('details')).toHaveCount(0);
  await expect(decision.getByText('为什么推荐？')).toHaveCount(0);

  // The rest of the agenda: same exercise title, two languages, two rows.
  const list = page.getByRole('region', { name: '今天接下来' });
  await expect(list.getByRole('listitem')).toHaveCount(2);
  await expect(list.getByRole('listitem').nth(0)).toContainText('C · 标记为需要加强');
  await expect(list.getByRole('listitem').nth(1)).toContainText('Python · 标记为需要加强');
  await expect(list.getByRole('listitem').nth(0).getByRole('link')).toHaveAttribute(
    'href',
    '/programming/C/exercises/11',
  );

  // The directions, each named after what it actually opens, and nothing that used to be here
  // instead of them.
  const spaces = page.getByRole('region', { name: '我的学习方向' });
  await expect(spaces.getByText('当前语言：C')).toBeVisible();
  await expect(spaces.getByRole('link', { name: /进入备考/ })).toBeVisible();
  await expect(spaces.getByRole('link', { name: /继续 C 编程/ })).toBeVisible();
  await expect(page.getByRole('heading', { name: '最近学习' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '去别的学习方向' })).toHaveCount(0);
  // 学习报告 is a header destination; the section beside the tasks no longer repeats it.
  await expect(page.getByRole('region', { name: '今天接下来' }).getByRole('link', { name: /学习报告/ }))
    .toHaveCount(0);

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);

  await page.screenshot({ path: 'test-results/home-explained-1440.png', fullPage: true });
});

test('Home holds its width at every breakpoint it is read at', async ({ page }) => {
  await stubHome(page);

  for (const size of [
    { width: 1600, height: 900 },
    { width: 1440, height: 900 },
    { width: 1024, height: 800 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    await page.goto('/');
    await expect(page.getByRole('region', { name: '现在先做' })).toBeVisible();

    // A page that scrolls sideways on a phone is the failure this catches: nothing may extend
    // past the viewport, at any of the widths the product is actually read at.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, `${size.width}px: home must not scroll sideways`).toBeLessThanOrEqual(0);

    // The three sections a learner reads today, in order, all on one screen.
    const decision = (await page.getByText('现在先做', { exact: true }).boundingBox())!;
    const directions = (await page.getByRole('heading', { name: '我的学习方向' }).boundingBox())!;
    expect(decision.y, `${size.width}px: the decision comes first`).toBeLessThan(directions.y);

    await page.screenshot({ path: `test-results/home-${size.width}.png`, fullPage: true });
  }
});

test('Home reports an empty agenda as an empty agenda, with every direction still reachable', async ({ page }) => {
  await stubHome(page);
  await page.route('**/learning/agenda**', (route) =>
    route.fulfill({ json: { ...AGENDA, items: [], total_items: 0 } }),
  );
  await page.goto('/');

  await expect(page.getByText('今天暂时没有需要优先处理的学习任务。')).toBeVisible();
  await expect(page.getByText('现在先做')).toHaveCount(0);
  const spaces = page.getByRole('region', { name: '我的学习方向' });
  await expect(spaces.getByRole('link')).toHaveCount(3);
});
