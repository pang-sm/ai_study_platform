import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('programming routes retain canonical language navigation and accessible workbench controls', async ({ page }) => {
  await page.goto('/programming/python/exercises/1');
  await expect(page.getByRole('heading', { name: '练习详情' })).toBeVisible();
  await page.goto('/programming/python/projects/1');
  await expect(page.getByRole('heading', { name: 'Python Workbench' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Test' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Submit' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI Explain' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI Debug' })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
