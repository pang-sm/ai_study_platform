import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('Home renders backend-ordered agenda evidence and safe action continuity', async ({ page }) => {
  await page.route('**/learning/agenda?**', (route) => route.fulfill({ json: { policy_version: 'v1', generated_at: '2026-09-20T00:00:00Z', items: [{ action_type: 'review', service_namespace: 'programming', domain_context: { language: 'python' }, source_type: 'review', source_id: 'r1', title: '复习数组边界', summary: '来自真实复习项', priority_reason: 'due_review', deep_link: '/review', due_at: null, facts: { due: true }, status: 'open', resolved_by: '完成复习' }], total_items: 1, source_summary: {}, semantics: 'facts' } }));
  await page.route('**/learning/agenda/explain?**', (route) => route.fulfill({ json: { reasons: { due_review: '复习项已到期。' } } }));
  await page.route('**/review/summary', (route) => route.fulfill({ json: { total: 1, by_namespace: {}, by_status: {}, by_source: {}, has_stored_due_dates: true, semantics: 'facts' } }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '今天接下来学什么' })).toBeVisible();
  await expect(page.getByText('复习数组边界')).toBeVisible();
  await page.getByText('为什么推荐这个？').click();
  await expect(page.getByText('完成什么动作后它会改变：完成复习')).toBeVisible();
  await expect(page.getByRole('link', { name: '打开并完成这项学习' })).toHaveAttribute('href', '/review');
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
