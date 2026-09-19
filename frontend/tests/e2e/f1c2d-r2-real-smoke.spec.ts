import { expect, test, type Page } from '@playwright/test';

const api = 'http://127.0.0.1:8952';
const practice = '/exam/cs408/practice?module=data_structure&chapter=1';

async function login(page: Page) {
  const response = await page.request.post(`${api}/login`, { data: { username: 'f1c2d_student', password: 'f1c2d-secret-123' } });
  expect(response.status()).toBe(200);
}

test('F1C2D R2 real smoke: confirmation is revealed and summary hides question controls', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page);
  await page.goto(practice);
  await page.getByRole('radio', { name: /元素之间的前后关系/ }).check();
  await page.getByRole('button', { name: '开始本章练习' }).click();
  await page.getByRole('button', { name: '提交本章答案' }).click();

  const continueButton = page.getByRole('button', { name: '继续作答' });
  await expect(continueButton).toBeFocused();
  expect((await continueButton.boundingBox())?.y).toBeLessThan(900);
  await continueButton.click();
  await expect(page.getByRole('button', { name: '提交本章答案' })).toBeFocused();

  await page.getByRole('button', { name: '提交本章答案' }).click();
  await page.getByRole('button', { name: '仍然提交' }).click();
  await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: '题目导航' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '上一题' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '下一题' })).toHaveCount(0);

  await page.getByRole('button', { name: '查看本次题目' }).click();
  await expect(page.getByRole('navigation', { name: '题目导航' })).toBeVisible();
  await expect(page.getByRole('button', { name: '下一题' })).toBeVisible();
});
