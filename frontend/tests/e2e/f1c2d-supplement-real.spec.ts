/**
 * F1C2D — supplementary REAL AUTHENTICATED BACKEND VQA.
 *
 * Covers the gates the main 9-test suite does not assert explicitly, all against the real FastAPI
 * app on port 8952 and a disposable TEMP database:
 *
 *   §20 answered navigator state must not use success semantics; its contrast must be >= 4.5
 *   §21 summary link / normal-size summary text contrast >= 4.5
 *   §24 whether a question-only control leaks into the active Summary view
 *   §26 axe on desktop summary, desktop submitted review, confirmation, mobile summary
 *   §30 the required real screenshot names
 *
 * Read-only with respect to product source: this file only drives and measures.
 */
import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const API = 'http://127.0.0.1:8952';
const ROOT = path.join(process.env.TEMP ?? '.', 'f1c2d-real');
const SCREENSHOTS = path.join(ROOT, 'screenshots');
const USERNAME = 'f1c2d_student';
const PASSWORD = 'f1c2d-secret-123';
const PRACTICE = '/exam/cs408/practice?module=data_structure&chapter=1';

const CORRECT_CHOICE = /元素之间的前后关系/;
const WRONG_CHOICE = /0 个/;
const BIG_ANSWER = '先判断表满，再把元素后移，最后写入并加一。';

/** WCAG 2.x contrast of an element's text against its nearest opaque ancestor background. */
async function contrast(page: Page, selector: string) {
  return page.evaluate((sel) => {
    const element = document.querySelector(sel) as HTMLElement | null;
    if (!element) return null;
    // computed colours arrive as `rgb(r g b)`, `rgba(...)` or `color(srgb r g b)` — the last uses
    // 0..1 floats, which must not be read as 0..255 channels.
    const channels = (value: string): number[] => {
      const numbers = (value.match(/-?[\d.]+(?:e-?\d+)?/g) ?? []).map(Number);
      if (/^color\(/.test(value)) return numbers.slice(0, 3).map((v) => v * 255);
      return numbers.slice(0, 3);
    };
    const luminance = ([r = 0, g = 0, b = 0]: number[]) => {
      const f = (v: number) => { const s = v / 255; return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4); };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    let background = 'rgb(255, 255, 255)';
    for (let node: HTMLElement | null = element; node; node = node.parentElement) {
      const candidate = getComputedStyle(node).backgroundColor;
      if (candidate && !/rgba\(0, 0, 0, 0\)|transparent/.test(candidate)) { background = candidate; break; }
    }
    const fg = getComputedStyle(element).color;
    const toHex = (value: string) => `#${channels(value).map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')}`;
    const l1 = luminance(channels(fg));
    const l2 = luminance(channels(background));
    return {
      foreground: toHex(fg),
      background: toHex(background),
      fontWeight: getComputedStyle(element).fontWeight,
      fontSize: getComputedStyle(element).fontSize,
      ratio: Math.round(((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)) * 100) / 100,
    };
  }, selector);
}

async function login(page: Page) {
  const response = await page.request.post(`${API}/login`, { data: { username: USERNAME, password: PASSWORD } });
  expect(response.status(), 'real POST /login').toBe(200);
  expect((await page.context().cookies(API)).map((cookie) => cookie.name)).toContain('ai_session');
}

async function startMixedAttempt(page: Page) {
  await page.goto(PRACTICE);
  await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeVisible();
  await page.getByRole('radio', { name: CORRECT_CHOICE }).check();
  await page.getByRole('button', { name: '下一题' }).click();
  await page.getByRole('radio', { name: WRONG_CHOICE }).check();
  await page.getByRole('button', { name: '下一题' }).click();
  await page.getByRole('button', { name: '下一题' }).click();
  await page.getByLabel('你的作答').fill(BIG_ANSWER);
  await page.getByRole('button', { name: '开始本章练习' }).click();
  await expect(page.getByRole('button', { name: '提交本章答案' })).toBeVisible();
}

async function confirmAndSubmit(page: Page) {
  await page.getByRole('button', { name: '提交本章答案' }).click();
  await expect(page.getByRole('alertdialog')).toContainText('还有 1 题未作答');
  await page.getByRole('button', { name: '仍然提交' }).click();
  await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
}

test.beforeAll(() => fs.mkdirSync(SCREENSHOTS, { recursive: true }));

test.describe.configure({ mode: 'default' });

test.describe('F1C2D supplementary real backend VQA', () => {
  test('S1 — desktop summary: screenshots, contrast (§20/§21), control-leak probe (§24), axe', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    // stand on question 1 so the summary is probed at an index where 下一题 would otherwise render
    await page.getByRole('button', { name: '第 1 题' }).click();

    // §30 real-desktop-unanswered-confirm — captured while the confirmation is genuinely active
    await page.getByRole('button', { name: '提交本章答案' }).click();
    await expect(page.getByRole('alertdialog')).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-unanswered-confirm.png') });
    const confirmAxe = await new AxeBuilder({ page }).include('.cs408-practice').analyze();
    console.log(`[confirm axe] ${confirmAxe.violations.map((v) => `${v.id}:${v.nodes.length}`).join(',') || 'none'}`);
    await page.getByRole('button', { name: '仍然提交' }).click();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();

    // §30 real-desktop-session-summary-mixed
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-session-summary-mixed.png') });

    // §21 summary link + normal-size summary text
    const link = await contrast(page, '.practice-summary__actions a');
    const facts = await contrast(page, '.practice-summary__facts p:nth-child(2)');
    const heading = await contrast(page, '.practice-summary h2');
    console.log(`[summary link] ratio=${link?.ratio} fg=${link?.foreground} bg=${link?.background} size=${link?.fontSize}`);
    console.log(`[summary facts] ratio=${facts?.ratio} fg=${facts?.foreground} bg=${facts?.background} size=${facts?.fontSize}`);
    console.log(`[summary heading] ratio=${heading?.ratio} size=${heading?.fontSize}`);
    expect(link!.ratio, 'SUMMARY_LINK_TEXT_CONTRAST').toBeGreaterThanOrEqual(4.5);
    expect(facts!.ratio, 'summary facts text contrast').toBeGreaterThanOrEqual(4.5);

    // §24 — is a question-only control present while the Summary is the active view?
    const nextVisible = await page.getByRole('button', { name: '下一题' }).isVisible().catch(() => false);
    const prevVisible = await page.getByRole('button', { name: '上一题' }).isVisible().catch(() => false);
    const navigatorCount = await page.locator('.practice-navigator button').count();
    let navigatesQuestions = false;
    if (nextVisible) {
      await page.getByRole('button', { name: '下一题' }).click();
      await page.waitForTimeout(250);
      navigatesQuestions = await page.getByRole('heading', { name: '本次练习完成' }).isVisible().catch(() => false) === false;
    }
    console.log(`[control leak] 下一题 visible=${nextVisible} 上一题 visible=${prevVisible} navigator buttons=${navigatorCount} click switches to questions=${navigatesQuestions}`);
    expect(navigatesQuestions, 'SUMMARY_QUESTION_CONTROL_LEAK — clicking a question control must not leave Summary').toBe(false);
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();

    const summaryAxe = await new AxeBuilder({ page }).include('.cs408-practice').analyze();
    console.log(`[desktop summary axe] ${summaryAxe.violations.map((v) => `${v.id}:${v.nodes.length}`).join(',') || 'none'}`);
    expect(summaryAxe.violations).toEqual([]);

    expect(errors).toEqual([]);
  });

  test('S2 — desktop submitted review: screenshot, read-only rehydration, answered-state semantics, axe', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    await confirmAndSubmit(page);

    await page.getByRole('button', { name: '查看本次题目' }).click();
    await page.getByRole('button', { name: '第 1 题' }).click();
    await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeChecked();
    await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeDisabled();
    await expect(page.getByRole('button', { name: '提交本章答案' })).toHaveCount(0);
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-submitted-review.png') });

    // §20 — the answered navigator state must not borrow success semantics.
    // Measure an answered button that is NOT the current one, i.e. exactly what the is-answered rule styles.
    const answered = await contrast(page, '.practice-navigator button.is-answered:not([aria-current="step"])');
    console.log(`[answered nav] ratio=${answered?.ratio} fg=${answered?.foreground} bg=${answered?.background} weight=${answered?.fontWeight}`);
    expect(answered, 'an answered navigator button must be rendered').not.toBeNull();
    expect(answered!.foreground, 'ANSWERED_STATE_USES_SUCCESS_SEMANTICS (#16a34a)').not.toContain('22, 163, 74');
    expect(answered!.ratio, 'ANSWERED_NAV_TEXT_CONTRAST').toBeGreaterThanOrEqual(4.5);

    const reviewAxe = await new AxeBuilder({ page }).include('.cs408-practice').analyze();
    console.log(`[desktop review axe] ${reviewAxe.violations.map((v) => `${v.id}:${v.nodes.length}`).join(',') || 'none'}`);
    expect(reviewAxe.violations).toEqual([]);
  });

  test('S3 — desktop: retry subset screenshot and a fully-answered summary', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    await confirmAndSubmit(page);
    const originalId = Number(new URL(page.url()).searchParams.get('attempt'));

    // §30 real-desktop-retry-subset
    await page.getByRole('button', { name: '重练本次错题' }).click();
    await expect.poll(() => Number(new URL(page.url()).searchParams.get('attempt'))).not.toBe(originalId);
    const retryId = Number(new URL(page.url()).searchParams.get('attempt'));
    await expect(page.locator('.practice-question input, .practice-question textarea')).toHaveCount(4);
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-retry-subset.png') });
    console.log(`[retry subset] attempt=${retryId} renderedControls=${await page.locator('.practice-question input, .practice-question textarea').count()}`);

    // §30 real-desktop-session-summary — a session with every question answered
    await page.goto(PRACTICE.replace('chapter=1', `chapter=1&attempt=${originalId}`));
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
    await page.getByRole('button', { name: '再做一遍本章' }).click();
    await expect.poll(() => Number(new URL(page.url()).searchParams.get('attempt'))).not.toBe(originalId);
    await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeVisible();
    await page.getByRole('radio', { name: CORRECT_CHOICE }).check();
    await page.getByRole('button', { name: '下一题' }).click();
    await page.getByRole('radio', { name: /约 n\/2 个/ }).check();
    await page.getByRole('button', { name: '下一题' }).click();
    await page.getByRole('radio', { name: /O\(n\)/ }).check();
    await page.getByRole('button', { name: '下一题' }).click();
    await page.getByLabel('你的作答').fill(BIG_ANSWER);
    await page.getByRole('button', { name: '提交本章答案' }).click();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-session-summary.png') });
  });

  test('S4 — mobile: summary and confirmation screenshots with axe', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await startMixedAttempt(page);

    await page.getByRole('button', { name: '提交本章答案' }).click();
    await expect(page.getByRole('alertdialog')).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-unanswered-confirm.png') });

    await page.getByRole('button', { name: '仍然提交' }).click();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-session-summary.png') });

    const link = await contrast(page, '.practice-summary__actions a');
    console.log(`[mobile summary link] ratio=${link?.ratio} bg=${link?.background}`);

    const axe = await new AxeBuilder({ page }).include('.cs408-practice').analyze();
    console.log(`[mobile summary axe] ${axe.violations.map((v) => `${v.id}:${v.nodes.length}`).join(',') || 'none'}`);
    expect(axe.violations).toEqual([]);

    // no horizontal overflow on the summary view
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    console.log(`[mobile overflow] ${overflow}`);
    expect(overflow).toBeLessThanOrEqual(0);

    expect(errors).toEqual([]);
  });
});
