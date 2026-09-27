import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { HARNESS, requiresHarness, signIn } from './support/session';

test.skip(requiresHarness.length > 0, requiresHarness.join(' '));

test('shared learning report keeps facts, deterministic insight, and AI narrative separate', async ({ page }) => {
  await signIn(page);
  // Origin-scoped: a path-only matcher would also answer the app's own navigation.
  await page.route((url) => url.origin === HARNESS.apiBase && url.pathname === '/ai/learning-report', async (route) => route.fulfill({ json: {
    report_id: 'report-python', report_period: { days: 7, start: '2026-09-13', end: '2026-09-20' }, context: { service_key: 'programming', language: 'python' }, data_coverage: { available_blocks: ['activity'], unavailable: [{ block: 'materials', reason: 'not_applicable_in_this_space' }] }, structured_metrics: { activity: { events: 0 }, materials: null }, highlights: [{ rule: 'activity_zero', origin: 'deterministic', text: '本周期没有活动' }], attention_items: [], narrative: { origin: 'ai', text: '这是基于上方事实的 AI 叙述。', capability: 'report.generate', request_id: 'request-1', usage: {} }, narrative_error: null, generated_at: '2026-09-20T10:00:00Z',
  } }));
  await page.goto('/reports?space=programming&language=python');
  await expect(page.getByRole('heading', { name: '学习报告' })).toBeVisible();
  await page.getByLabel('包含 AI 叙述（会消耗额度）').check();
  await page.getByRole('button', { name: '生成学习报告' }).click();
  // The deterministic block comes first and the model's own prose last, under its own heading —
  // the separation is the thing this spec exists to protect.
  await expect(page.getByRole('heading', { name: '本周期做成了什么' })).toBeVisible();
  await expect(page.getByText('本周期没有活动')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'AI 叙述' })).toBeVisible();
  await expect(page.getByText('这是基于上方事实的 AI 叙述。')).toBeVisible();
  // And the block states where its own text came from.
  await expect(page.getByText('来源：AI 生成').first()).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
