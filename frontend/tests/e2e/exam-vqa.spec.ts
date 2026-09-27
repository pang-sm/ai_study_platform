import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const enabled = process.env.EXAM_VQA === '1';
const backend = 'http://127.0.0.1:8017';
const screenshotDir = path.join(process.env.TEMP ?? '.', 'zhixue-f1b1-vqa', 'screenshots');

/** The four papers of 408, as the catalogue keys them. */
const MODULE_KEY: Readonly<Record<string, string>> = {
  数据结构: 'data_structure',
  计算机组成原理: 'computer_organization',
  操作系统: 'operating_system',
  计算机网络: 'computer_network',
};

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
    // The exam space has no space-level tab bar: it is one page whose first block is 我的考试科目,
    // with 考试方案 summarised under it. Every exam page states its own identity — and the
    // space's own name is not repeated as a title, because the global navigation already says it.
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('heading', { name: '考研学习' })).toHaveCount(0);
    await expect(page.getByRole('navigation', { name: '考研学习导航' })).toHaveCount(0);
    await assertHealthy(page, screenshot);
  }

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/exam');
  const plan = page.getByRole('region', { name: '考试方案' });
  await expect(plan.getByText('2027 全国硕士研究生招生考试（统考）')).toBeVisible();
  // The subjects are the block above the summary, not a list repeated inside it.
  await expect(page.getByRole('region', { name: '我的考试科目' }).getByText('数学（一）')).toBeVisible();
  await expect(plan.getByText('数学（一）')).toHaveCount(0);
  await page.goto('/exam/subjects/math_1');
  // A framework-only subject opens its own status page, not an empty shell.
  await expect(page.getByText('当前状态')).toBeVisible();
  await expect(page.getByText('科目框架已建立')).toBeVisible();
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
  await expect(page.getByText('还没有考试方案。')).toBeVisible();
  await expect(page.getByRole('link', { name: '设置考试方案' })).toBeVisible();
  await assertHealthy(page, 'tablet-exam-unconfigured.png');
});

test('CS408 front door is four papers, each carrying its own real state', async ({ page }) => {
  await useQaSession(page, 'f1b1-vqa-session-token');
  for (const [viewport, screenshot] of [
    [{ width: 1440, height: 900 }, 'desktop-cs408-home.png'],
    [{ width: 1024, height: 768 }, 'tablet-cs408-home.png'],
    [{ width: 390, height: 844 }, 'mobile-cs408-home.png'],
  ] as const) {
    await page.setViewportSize(viewport);
    await page.goto('/exam/cs408');
    await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible();
    for (const paper of ['数据结构', '计算机组成原理', '操作系统', '计算机网络']) {
      await expect(page.getByRole('link', { name: new RegExp(`^${paper}`) })).toHaveAttribute(
        'href',
        `/exam/cs408?module=${MODULE_KEY[paper]}`,
      );
    }
    await assertHealthy(page, screenshot);
  }
});

test('one paper’s state failing leaves the other three usable and says nothing about the fourth', async ({ page }) => {
  await useQaSession(page, 'f1b1-vqa-session-token');
  await page.route('**/exam/11408/subjects/operating_system/dashboard-summary', (route) => route.fulfill({ status: 503, body: JSON.stringify({ detail: 'temporary' }) }));
  await page.goto('/exam/cs408');
  await expect(page.getByRole('heading', { name: '选择学习科目' })).toBeVisible();

  // The three papers whose summaries arrived state their position; the one that failed is still a
  // way in, and says nothing about itself rather than inventing a state or leaking the failure.
  for (const paper of ['数据结构', '计算机组成原理', '计算机网络']) {
    await expect(page.getByRole('link', { name: new RegExp(`^${paper}(尚未开始|学习中|已学习)$`) })).toBeVisible();
  }
  await expect(page.getByRole('link', { name: '操作系统', exact: true })).toBeVisible();
  await expect(page.getByText(/无法加载|重试|503|temporary/)).toHaveCount(0);
});

test('CS408 new-user state suppresses zero-metric dashboard copy', async ({ page }) => {
  await useQaSession(page, 'f1b1-vqa-empty-token');
  await page.goto('/exam/cs408');
  // A paper with nothing recorded reads as a state, not as 0%.
  await expect(page.getByText('尚未开始', { exact: true })).toHaveCount(4);
  await expect(page.getByText(/0%/)).toHaveCount(0);
  await expect(page.getByText(/已学习 0 分钟/)).toHaveCount(0);
});
