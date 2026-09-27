import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { requiresHarness, signIn } from './support/session';

// Migrated to the canonical authenticated contract.
//
// Two things had gone stale. The spec never signed in, which the root guard has refused for every
// learning surface since the auth work landed — so it could not pass and was usually reported as
// "did not run". And its assertions named an older workbench in English ("Python Workbench", "Run",
// "Test", "AI Explain"); this build states the same three tool tiers in the product's own words,
// and the deterministic compiler check is deliberately NOT called AI.
//
// The tiers are what the spec is about, so they are asserted as they are now: 运行 / 运行测试 / 提交
// are the execution tier, 运行代码诊断 is the compiler, AI Debug is the single-call AI tier, and the
// multi-step Debug Agent workflow sits behind the fold.
test.skip(requiresHarness.length > 0, requiresHarness.join(' '));

test('programming routes retain canonical language navigation and accessible workbench controls', async ({ page }) => {
  await signIn(page);

  await page.goto('/programming/python/exercises/1');
  await expect(page.getByRole('heading', { name: '练习题面' })).toBeVisible();

  await page.goto('/programming/python/projects/1');
  await expect(page.getByRole('heading', { name: '编写代码' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '执行反馈' })).toBeVisible();

  for (const control of ['运行', '运行测试', '提交', '运行代码诊断']) {
    await expect(page.getByRole('button', { name: control, exact: true })).toBeVisible();
  }
  await expect(page.getByRole('button', { name: 'AI Debug', exact: true })).toBeVisible();

  await page.getByText('高级工作流：Debug Agent').click();
  await expect(page.getByRole('button', { name: '启动 Debug Agent' })).toBeVisible();

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
