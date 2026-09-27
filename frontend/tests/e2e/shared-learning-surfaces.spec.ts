import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { HARNESS, requiresHarness, signIn } from './support/session';

// Migrated to the canonical authenticated contract.
//
// The spec never signed in, and its second half used an older workbench's words ("Review Patch",
// English controls). Both are corrected here; the assertions it was written for — the shared review
// surface filters by space, and the multi-step workflow produces a patch it can apply to the
// buffer — are kept, now as two tests so a failure in one is not reported as a failure of both.
test.skip(requiresHarness.length > 0, requiresHarness.join(' '));

test('the shared review surface names the space each item came from', async ({ page }) => {
  await signIn(page);

  // Matched on the API ORIGIN, not on a path: a path-only matcher also intercepts the app's own
  // navigation to /review and answers it with JSON, so the browser renders the payload instead of
  // the page. (It did, and the failure looked like a missing heading.)
  const onApi = (pathname: string) => (url: URL) => url.origin === HARNESS.apiBase && url.pathname === pathname;
  await page.route(onApi('/review/summary'), async (route) => route.fulfill({ json: { total: 1, by_namespace: { programming: 1 }, by_status: { needs_attention: 1 }, by_source: {}, has_stored_due_dates: false, semantics: 'stored facts' } }));
  await page.route(onApi('/review'), async (route) => route.fulfill({ json: { items: [{ id: 'p1', service_namespace: 'programming', domain_context: {}, source_type: 'needs_work', source_id: '1', title: '修复边界', summary: '', review_status: 'needs_attention', due_at: null, reason: '测试失败', deep_link: '/programming/python/errors' }], total: 1, limit: 100, offset: 0, buckets: {}, semantics: 'stored facts' } }));

  await page.goto('/review');
  await expect(page.getByRole('heading', { name: '统一复习' })).toBeVisible();
  await expect(page.getByText('修复边界')).toBeVisible();
  // The filters are the spaces themselves, so an item can be traced to where it came from.
  await expect(page.getByRole('button', { name: '编程' })).toBeVisible();
  await expect(page.getByRole('button', { name: '专业学习' })).toBeVisible();

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test('the multi-step Debug Agent workflow yields a patch that can be applied to the buffer', async ({ page }) => {
  await signIn(page);

  await page.route((url) => url.origin === HARNESS.apiBase && url.pathname === '/programming/agent/debug', async (route) => route.fulfill({ json: { agent_run_id: 'a1', status: 'completed', language: 'python', steps: [{ step_index: 1, action: 'diagnosis', status: 'completed', file_type: 'analysis', snippet: '诊断' }], iterations_used: 1, executions_used: 1, diagnosis: '边界错误', patch_summary: '', explanation: '修复说明', proposed_patch: '- 1\n+ 0', final_code: 'print(0)', usage: { model_steps: 1, execution_steps: 1, actual_credits: 1, estimated_credits: 1 } } }));

  await page.goto('/programming/python/projects/1');
  await expect(page.getByRole('heading', { name: '编写代码' })).toBeVisible();

  // Scoped to the textbox: a loose label match also resolves 编写代码 (the section) and
  // AI 代码分析 (the AI panel), which is a strict-mode violation rather than a missing element.
  const editor = page.getByRole('textbox', { name: '代码', exact: true });
  await expect(editor).toBeVisible({ timeout: 20_000 });
  await editor.fill('print(1)');

  // The multi-step workflow is behind a fold until it is asked for.
  await page.getByText('高级工作流：Debug Agent').click();
  await page.getByRole('button', { name: '启动 Debug Agent' }).click();

  const apply = page.getByRole('button', { name: '应用到编辑器' });
  await expect(apply).toBeVisible({ timeout: 20_000 });
  await apply.click();
  await expect(editor).toHaveValue('print(0)');

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
