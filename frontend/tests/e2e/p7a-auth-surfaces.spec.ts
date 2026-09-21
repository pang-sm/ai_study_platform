import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// These specs cover the sign-in surfaces and the guard's behaviour when the API cannot answer.
// They deliberately need NO backend: `/login` and `/register` must render on their own, and the
// refusal to invent a signed-in view is exactly what is being asserted.

test('login page renders, validates locally and is accessible', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  await page.goto('/login');
  await expect(page.getByRole('heading', { name: '登录', level: 1 })).toBeVisible();

  await page.getByRole('button', { name: '登录' }).click();
  await expect(page.getByText('请输入账号或邮箱')).toBeVisible();
  await expect(page.getByText('请输入密码')).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

test('register page verifies the email before it asks for account details', async ({ page }) => {
  await page.goto('/register');
  await expect(page.getByRole('heading', { name: '注册', level: 1 })).toBeVisible();
  // `exact` matters: the code field is labelled 邮箱验证码 and would otherwise also match.
  await expect(page.getByLabel('邮箱', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '发送验证码' })).toBeVisible();
  // No account fields, and no "forgot password" flow that the API does not implement.
  await expect(page.getByLabel('账号', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: /忘记密码|找回密码/ })).toHaveCount(0);

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test('sign-in surfaces have no horizontal overflow at desktop and mobile widths', async ({ page }) => {
  for (const size of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    for (const path of ['/login', '/register']) {
      await page.goto(path);
      const hasOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
      );
      expect(hasOverflow, `${path} at ${size.width}px`).toBe(false);
    }
  }
});

test('a protected route reports the failure instead of guessing when the API is unreachable', async ({ page }) => {
  await page.goto('/exam/cs408/practice');

  // With no reachable session probe the app cannot know whether this visitor is signed in, so it
  // must not render a protected surface and must not claim to be signed out either.
  await expect(page.getByRole('heading', { name: '出错了' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '选择学习模块' })).toHaveCount(0);
});

test('the sign-in page is still reachable while the session probe fails', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByRole('heading', { name: '登录', level: 1 })).toBeVisible();
  await expect(page.getByRole('heading', { name: '出错了' })).toHaveCount(0);
});
