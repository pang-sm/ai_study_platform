import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const enabled = process.env.EXAM_VQA === '1';
const backend = 'http://127.0.0.1:8017';
const screenshotDir = path.join(process.env.TEMP ?? '.', 'zhixue-f1b1-vqa', 'screenshots');

test.skip(!enabled, 'Run only against the temporary F1B1 VQA backend.');

async function useQaSession(page: Page, token: string) {
  const forwardExamRequest = async (route: Route) => {
    const request = route.request();
    const response = await page.request.fetch(`${backend}${new URL(request.url()).pathname}`, {
      method: request.method(),
      headers: { cookie: `ai_session=${token}`, 'content-type': (await request.headerValue('content-type')) ?? 'application/json' },
      data: request.postData() ?? undefined,
    });
    await route.fulfill({ status: response.status(), headers: response.headers(), body: await response.body() });
  };
  await page.route('**/exam/prep/**', forwardExamRequest);
  await page.route('**/exam/11408/**', forwardExamRequest);
}

async function assertHealthy(page: Page, screenshot: string) {
  await expect(page.locator('main')).not.toBeEmpty();
  await expect(page.locator('h1')).toBeVisible();
  expect(await new AxeBuilder({ page }).analyze()).toMatchObject({ violations: [] });
  await page.screenshot({ path: path.join(screenshotDir, screenshot), fullPage: false });
}

test.beforeAll(() => fs.mkdirSync(screenshotDir, { recursive: true }));

test('authenticated real-contract configured profile visual acceptance', async ({ page }) => {
  test.setTimeout(60_000);
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().includes('409 (Conflict)')) consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.message));
  await useQaSession(page, 'f1b1-vqa-session-token');

  for (const [surface, viewport, screenshot] of [
    ['/exam', { width: 1440, height: 900 }, 'desktop-exam-redesign.png'],
    ['/exam/setup', { width: 1440, height: 900 }, 'desktop-setup-redesign.png'],
    ['/exam/subjects', { width: 1440, height: 900 }, 'desktop-subjects-redesign.png'],
    ['/exam/subjects/math_1', { width: 1440, height: 900 }, 'desktop-framework-redesign.png'],
    ['/exam', { width: 390, height: 844 }, 'mobile-exam-redesign.png'],
    ['/exam/setup', { width: 390, height: 844 }, 'mobile-setup-redesign.png'],
    ['/exam/subjects', { width: 390, height: 844 }, 'mobile-subjects-redesign.png'],
    ['/exam', { width: 1024, height: 768 }, 'tablet-exam-redesign.png'],
  ] as const) {
    await page.setViewportSize(viewport);
    await page.goto(surface);
    await expect(page.getByRole('navigation', { name: '考研学习导航' })).toBeVisible();
    await assertHealthy(page, screenshot);
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/exam');
  await expect(page.getByText('目标考试年份 · 2027')).toBeVisible();
  await expect(page.getByText('数学（一）')).toBeVisible();
  await expect(page.getByRole('link', { name: '进入 CS408' })).toBeVisible();
  await page.goto('/exam/subjects/math_1');
  await expect(page.getByText('这门科目已加入你的备考范围。')).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test('homepage visual regression check', async ({ page }) => {
  for (const [viewport, screenshot] of [
    [{ width: 1440, height: 900 }, 'homepage-after-redesign-desktop.png'],
    [{ width: 390, height: 844 }, 'homepage-after-redesign-mobile.png'],
  ] as const) {
    await page.setViewportSize(viewport);
    await page.goto('/');
    await assertHealthy(page, screenshot);
  }
});

test('authenticated unconfigured profile visual acceptance', async ({ page }) => {
  await useQaSession(page, 'f1b1-vqa-empty-token');
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/exam');
  await expect(page.getByRole('heading', { name: '开始设置你的备考范围' })).toBeVisible();
  await expect(page.getByRole('link', { name: '设置我的备考' })).toBeVisible();
  await assertHealthy(page, 'tablet-exam-unconfigured.png');
});

test('CS408 workspace visual acceptance retains per-module states', async ({ page }) => {
  await useQaSession(page, 'f1b1-vqa-session-token');
  for (const [viewport, screenshot] of [
    [{ width: 1440, height: 900 }, 'desktop-cs408-home.png'],
    [{ width: 1024, height: 768 }, 'tablet-cs408-home.png'],
    [{ width: 390, height: 844 }, 'mobile-cs408-home.png'],
  ] as const) {
    await page.setViewportSize(viewport);
    await page.goto('/exam/cs408');
    await expect(page.getByRole('heading', { name: '学习工作区' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '数据结构' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '计算机网络' })).toBeVisible();
    await assertHealthy(page, screenshot);
  }
});

test('CS408 workspace keeps three modules usable when one summary request fails', async ({ page }) => {
  await useQaSession(page, 'f1b1-vqa-session-token');
  await page.route('**/exam/11408/subjects/operating_system/dashboard-summary', (route) => route.fulfill({ status: 503, body: JSON.stringify({ detail: 'temporary' }) }));
  await page.goto('/exam/cs408');
  await expect(page.getByRole('heading', { name: '数据结构' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '计算机组成原理' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '操作系统' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '计算机网络' })).toBeVisible();
  await expect(page.getByText('此模块暂时无法加载。')).toBeVisible();
  await expect(page.getByRole('button', { name: '重试操作系统模块' })).toBeVisible();
});

test('CS408 new-user state suppresses zero-metric dashboard copy', async ({ page }) => {
  await useQaSession(page, 'f1b1-vqa-empty-token');
  await page.goto('/exam/cs408');
  await expect(page.getByText('尚未开始学习')).toHaveCount(4);
  await expect(page.getByText('知识点已学习 0%')).toHaveCount(0);
  await expect(page.getByText('已学习 0 分钟')).toHaveCount(0);
});
