import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const backend = process.env.F1C1_VQA_BACKEND ?? 'http://127.0.0.1:8018';
const token = process.env.F1C1_VQA_TOKEN;
const screenshots = path.join(process.env.TEMP ?? '.', 'zhixue-f1c1-vqa', 'screenshots');

test.skip(!token, 'requires the real temporary authenticated session');

async function authenticate(page: Page) {
  await page.route('**/exam/11408/**', async (route: Route) => {
    const request = route.request();
    const response = await page.request.fetch(`${backend}${new URL(request.url()).pathname}`, { method: request.method(), headers: { cookie: `ai_session=${token}`, 'content-type': (await request.headerValue('content-type')) ?? 'application/json' }, data: request.postData() ?? undefined });
    await route.fulfill({ status: response.status(), headers: response.headers(), body: await response.body() });
  });
}

async function axe(page: Page) { expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]); }

test.beforeAll(() => fs.mkdirSync(screenshots, { recursive: true }));

test('real authenticated CS408 knowledge VQA and PATCH', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', (error) => errors.push(error.message));
  await authenticate(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/exam/cs408/knowledge?module=data_structure');
  // The page names its tool; which paper it is open in is stated once, by the workspace header.
  await expect(page.getByRole('heading', { name: '知识脉络' })).toBeVisible();
  await expect(page.getByText('408 · 数据结构')).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-knowledge-data-structure.png') });
  await page.getByRole('button', { name: /展开 / }).nth(1).click();
  await page.getByRole('button', { name: /展开 / }).nth(1).click();
  await page.getByRole('button', { name: /展开 / }).nth(1).click();
  const leaf = page.getByRole('button', { name: /选择 / }).first();
  await leaf.click();
  await expect(page.getByText('我的学习状态')).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-knowledge-selected-point.png') });
  await page.getByRole('button', { name: '更新学习状态' }).click();
  await page.getByRole('button', { name: '已学习' }).click();
  await expect(page.locator('.knowledge-detail').getByText('已学习')).toBeVisible();
  await axe(page);
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.screenshot({ path: path.join(screenshots, 'tablet-knowledge.png') });
  await axe(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('.knowledge-detail').scrollIntoViewIfNeeded();
  await expect(page.getByRole('heading', { name: /算法的基本概念/ })).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'mobile-knowledge-detail.png') });
  await axe(page);
  await page.goto('/exam/cs408/knowledge?module=operating_system');
  await expect(page.getByRole('heading', { name: '知识脉络' })).toBeVisible();
  await expect(page.getByText('408 · 操作系统')).toBeVisible();
  await expect(page.getByRole('button', { name: /展开 / }).first()).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'mobile-knowledge-outline.png') });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: path.join(screenshots, 'desktop-knowledge-operating-system.png') });
  await axe(page);
  // The paper that was just edited reports it. `/exam/cs408` with no module is the subject's
  // front door and states a paper's position only as one word, so the reading above lives in the
  // paper's own 概览 — which is where a learner lands on 继续学习 · 数据结构 from the home.
  await page.goto('/exam/cs408?module=data_structure');
  await expect(page.getByRole('heading', { name: '概览' })).toBeVisible();
  await expect(page.getByText(/知识点已学习比例 [1-9]\d*%/).first()).toBeVisible();
  await page.screenshot({ path: path.join(screenshots, 'desktop-cs408-populated-after-knowledge.png') });
  expect(errors).toEqual([]);
});

test('CS408 routes into a paper, keeps the deep link, and states its own way back', async ({ page }) => {
  await authenticate(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/exam/cs408');

  // The front door asks which of the four papers to study — four ways in and nothing else.
  await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible();
  for (const paper of ['数据结构', '计算机组成原理', '操作系统', '计算机网络']) {
    await expect(page.getByRole('link', { name: new RegExp(`^${paper}`) })).toBeVisible();
  }

  await page.getByRole('link', { name: /^数据结构/ }).click();
  await expect(page).toHaveURL(/\/exam\/cs408\?module=data_structure$/);
  await expect(page.getByRole('heading', { name: '概览' })).toBeVisible();
  await expect(page.getByText('408 · 数据结构')).toBeVisible();

  await page.getByRole('link', { name: '知识脉络' }).click();
  await expect(page).toHaveURL(/\/exam\/cs408\/knowledge\?module=data_structure$/);
  await expect(page.getByRole('heading', { name: '知识脉络' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '选择学习科目' })).toHaveCount(0);

  // A deep link is stable: the module is in the URL, not in a remembered preference.
  await page.reload();
  await expect(page).toHaveURL(/\/exam\/cs408\/knowledge\?module=data_structure$/);
  await expect(page.getByRole('heading', { name: '知识脉络' })).toBeVisible();
  await expect(page.getByText('408 · 数据结构')).toBeVisible();

  // The way out is the page's own, so it is the same one whether the page was reached by
  // clicking through or by pasting the URL into a fresh tab.
  await page.getByRole('link', { name: '返回 408', exact: true }).click();
  await expect(page).toHaveURL(/\/exam\/cs408$/);
  await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible();

  await page.goto('/exam/cs408/knowledge?module=operating_system');
  await expect(page.getByRole('link', { name: '返回 408', exact: true })).toHaveAttribute(
    'href',
    '/exam/cs408',
  );
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});
