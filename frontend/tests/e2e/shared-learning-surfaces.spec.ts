import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('shared review and evidence-based advanced workflows are explicit and accessible', async ({ page }) => {
  await page.route('**/review/summary', async (route) => route.fulfill({ json: { total: 1, by_namespace: { programming: 1 }, by_status: { needs_attention: 1 }, by_source: {}, has_stored_due_dates: false, semantics: 'stored facts' } }));
  await page.route('**/review?**', async (route) => route.fulfill({ json: { items: [{ id: 'p1', service_namespace: 'programming', domain_context: {}, source_type: 'needs_work', source_id: '1', title: '修复边界', summary: '', review_status: 'needs_attention', due_at: null, reason: '测试失败', deep_link: '/programming/python/errors' }], total: 1, limit: 100, offset: 0, buckets: {}, semantics: 'stored facts' } }));
  await page.goto('/review');
  await expect(page.getByRole('heading', { name: '统一复习' })).toBeVisible();
  await expect(page.getByText('待处理 / 未设日期')).toBeVisible();
  await expect(page.getByRole('button', { name: '编程' })).toBeVisible();
  await page.route('**/programming/agent/debug', async (route) => route.fulfill({ json: { agent_run_id: 'a1', status: 'completed', language: 'python', steps: [{ step_index: 1, action: 'diagnosis', status: 'completed', file_type: 'analysis', snippet: '诊断' }], iterations_used: 1, executions_used: 1, diagnosis: '边界错误', patch_summary: '', explanation: '修复说明', proposed_patch: '- 1\n+ 0', final_code: 'print(0)', usage: { model_steps: 1, execution_steps: 1, actual_credits: 1, estimated_credits: 1 } } }));
  await page.goto('/programming/python/projects/1');
  await page.getByLabel('代码').fill('print(1)');
  await page.getByRole('button', { name: '启动 Debug Agent' }).click();
  await expect(page.getByText('Review Patch')).toBeVisible();
  await page.getByRole('button', { name: '应用到编辑器' }).click();
  await expect(page.getByLabel('代码')).toHaveValue('print(0)');
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
