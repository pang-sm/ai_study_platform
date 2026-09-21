import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('shared learning report keeps facts, deterministic insight, and AI narrative separate', async ({ page }) => {
  await page.route('**/ai/learning-report', async (route) => route.fulfill({ json: {
    report_id: 'report-python', report_period: { days: 7, start: '2026-09-13', end: '2026-09-20' }, context: { service_key: 'programming', language: 'python' }, data_coverage: { available_blocks: ['activity'], unavailable: [{ block: 'materials', reason: 'not_applicable_in_this_space' }] }, structured_metrics: { activity: { events: 0 }, materials: null }, highlights: [{ rule: 'activity_zero', origin: 'deterministic', text: '本周期没有活动' }], attention_items: [], narrative: { origin: 'ai', text: '这是基于上方事实的 AI 叙述。', capability: 'report.generate', request_id: 'request-1', usage: {} }, narrative_error: null, generated_at: '2026-09-20T10:00:00Z',
  } }));
  await page.goto('/reports?space=programming&language=python');
  await expect(page.getByRole('heading', { name: '学习报告' })).toBeVisible();
  await page.getByLabel('包含 AI Narrative').check();
  await page.getByRole('button', { name: '生成学习报告' }).click();
  await expect(page.getByRole('heading', { name: 'Structured Facts' })).toBeVisible();
  await expect(page.getByText('unavailable').first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Deterministic highlights / attention' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'AI Narrative' })).toBeVisible();
  await expect(page.getByText('这是基于上方事实的 AI 叙述。')).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
