import { expect, test } from '@playwright/test';

const moduleKeys = [
  'data_structure',
  'computer_organization',
  'operating_system',
  'computer_network',
] as const;

const moduleNames = ['数据结构', '计算机组成原理', '操作系统', '计算机网络'] as const;

test('unified review presents factual question titles and normalized directions responsively', async ({ page }) => {
  const snoozed = new Set<string>();
  let stemReads = 0;
  let selectedNamespace = '';

  const items = [
    ...moduleKeys.map((module, index) => ({
      recommendation_key: `exam-${module}`,
      kind: 'question',
      service_namespace: 'exam_prep',
      domain_context: { exam_module_id: module },
      title: `题目 ${1686572 + index}`,
      direction: `11408 · ${module}`,
      reason_code: 'single_wrong',
      reason: '这道题有一次尚未订正的真实错误',
      evidence: { source_id: String(50 + index) },
      action: { deep_link: `/exam/cs408/wrong?module=${module}` },
    })),
    {
      recommendation_key: 'course-review',
      kind: 'knowledge',
      service_namespace: 'course_learning',
      domain_context: { course_id: 'course-123' },
      title: '集合运算与关系',
      direction: '专业学习 · course-123',
      reason_code: 'scheduled_overdue',
      reason: '已有复习计划已到期',
      evidence: {},
      action: { deep_link: '/course/course-123/study?knowledge_point_id=12' },
    },
    {
      recommendation_key: 'programming-review',
      kind: 'programming_exercise',
      service_namespace: 'programming',
      domain_context: { language: 'python', exercise_id: 'exercise-8' },
      title: '滑动窗口最大值',
      direction: '编程 · python',
      reason_code: 'programming_single_failure',
      reason: '最近一次真实提交未通过',
      evidence: {},
      action: { deep_link: '/programming/workbench?language=Python&exercise=exercise-8' },
    },
  ];

  await page.route(/\/me$/, (route) => {
    return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ user: { id: 991, username: 'review-presentation-e2e' } }),
    });
  });
  await page.route(/\/review\/recommendations(?:\?.*)?$/, async (route) => {
    const url = new URL(route.request().url());
    selectedNamespace = url.searchParams.get('service_namespace') ?? '';
    const filtered = items.filter((item) => {
      const namespaceMatches = !selectedNamespace
        || (selectedNamespace === 'exam_11408' && item.service_namespace === 'exam_prep')
        || item.service_namespace === selectedNamespace;
      return namespaceMatches && !snoozed.has(item.recommendation_key);
    });
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ total: filtered.length, items: filtered, policy_version: 'e2e', generated_at: '2026-10-09T00:00:00Z', limit: 200, offset: 0 }),
    });
  });
  await page.route(/\/wrong-answers(?:\?.*)?$/, async (route) => {
    stemReads += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total: 4,
        limit: 200,
        offset: 0,
        items: moduleKeys.map((_, index) => ({
          wrong_record_id: 50 + index,
          status: 'active',
          stem: `真实题干摘要 ${index + 1}：按题目给出的条件判断处理顺序。`,
          reference_answer: '不应出现在复习卡片中的参考答案',
          analysis: '不应出现在复习卡片中的解析',
        })),
      }),
    });
  });
  await page.route(/\/course-learning\/courses(?:\?.*)?$/, (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ courses: [{ course_id: 'course-123', course_name: '离散数学' }], total: 1 }),
  }));
  await page.route(/\/review\/recommendations\/[^/]+\/snooze$/, async (route) => {
    const key = route.request().url().split('/').at(-2) ?? '';
    snoozed.add(decodeURIComponent(key));
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ recommendation_key: key, snoozed_until: '2026-10-10T00:00:00Z' }) });
  });

  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/review');
  await expect(page.getByRole('heading', { name: '统一复习' })).toBeVisible();
  await expect(page.getByText('真实题干摘要 1：按题目给出的条件判断处理顺序。')).toBeVisible();
  for (const name of moduleNames) await expect(page.getByText(`11408 · ${name}`)).toBeVisible();
  await expect(page.getByText('专业学习 · 离散数学')).toBeVisible();
  await expect(page.getByText('编程 · Python')).toBeVisible();
  await expect(page.getByText('不应出现在复习卡片中的参考答案')).toHaveCount(0);
  await expect(page.getByText('不应出现在复习卡片中的解析')).toHaveCount(0);
  await expect(page.getByText(/题目\s+1686572/)).toHaveCount(0);
  await expect(page.locator('ol')).toHaveClass(/space-y-3/);
  await expect(page.locator('a', { hasText: '开始复习' }).first()).toHaveAttribute('href', /\/exam\/cs408\/wrong\?module=/);
  expect(stemReads).toBe(1);

  await page.getByRole('button', { name: '11408', exact: true }).click();
  await expect(page.getByText('编程 · Python')).toHaveCount(0);
  await expect(page.getByText('真实题干摘要 4：按题目给出的条件判断处理顺序。')).toBeVisible();
  expect(selectedNamespace).toBe('exam_11408');

  await page.getByRole('button', { name: '暂缓' }).first().click();
  await expect(page.getByText('真实题干摘要 1：按题目给出的条件判断处理顺序。')).toHaveCount(0);
  await expect(page.getByText('真实题干摘要 2：按题目给出的条件判断处理顺序。')).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole('heading', { name: '统一复习' })).toBeVisible();
  await expect(page.getByText('真实题干摘要 1：按题目给出的条件判断处理顺序。')).toHaveCount(0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBe(0);
  const clamp = await page.getByRole('heading', { name: '真实题干摘要 2：按题目给出的条件判断处理顺序。' }).evaluate((node) => getComputedStyle(node).webkitLineClamp);
  expect(clamp).toBe('2');
  expect(consoleErrors).toEqual([]);
});
