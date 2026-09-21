import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('course workspace keeps course context in responsive navigation and has no axe violations', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/course/cs101');

  const navigation = page.getByRole('navigation', { name: '课程学习导航' });
  await expect(navigation.getByRole('link', { name: '概览' })).toHaveAttribute('aria-current', 'page');
  await expect(navigation.getByRole('link', { name: '资料' })).toHaveAttribute('href', '/course/cs101/materials');
  await expect(page.getByRole('heading', { name: 'cs101' })).toBeVisible();

  const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(hasOverflow).toBe(false);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
