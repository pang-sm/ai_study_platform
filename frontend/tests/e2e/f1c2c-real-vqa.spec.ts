/**
 * F1C2C — REAL AUTHENTICATED BACKEND VQA.
 *
 * Unlike `f1c2c-vqa.spec.ts` (route-level doubles), this spec runs against the REAL FastAPI app on
 * port 8951 backed by a disposable TEMP database:
 *
 *   - real `POST /login` → real bcrypt check → real `auth_sessions` row → real `ai_session` cookie;
 *   - real chapter-practice attempt creation, answer save, submit and submitted-detail replay;
 *   - real `POST /exam/11408/{subject_key}/question-analysis` through the real orchestrator
 *     (permission → router → estimate → reserve → provider → cost → settle). Only the outbound
 *     provider transport is a local deterministic double, installed below the orchestrator boundary
 *     in the harness; no paid provider is ever constructed or called.
 */
import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const API = 'http://127.0.0.1:8951';
const ROOT = path.join(process.env.TEMP ?? '.', 'f1c2c-real');
const SCREENSHOTS = path.join(ROOT, 'screenshots');
const CONTROL = path.join(ROOT, 'double_control.json');
const CALLS = path.join(ROOT, 'double_calls.jsonl');
const USERNAME = 'vqa_student';
const PASSWORD = 'vqa-secret-123';
const PRACTICE = '/exam/cs408/practice?module=data_structure&chapter=1';
const CORRECT_OPTION = /元素之间的前后关系/;
const WRONG_OPTION = /元素在内存中的存储地址/;
const EXPLAIN_TEXT = 'VQA 双替身生成的讲解内容。';
const BIG_STATIC_ANALYSIS = '要点：容量校验';

function setDouble(behavior: string, delayMs = 0, content?: string) {
  fs.writeFileSync(CONTROL, JSON.stringify({ behavior, delay_ms: delayMs, content: content ?? EXPLAIN_TEXT }), 'utf-8');
}

function doubleCalls(): Array<Record<string, unknown>> {
  if (!fs.existsSync(CALLS)) return [];
  return fs.readFileSync(CALLS, 'utf-8').trim().split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

type RequestLog = { url: string; body: Record<string, unknown> | null; response: unknown };

/** Every API path the browser touches, so forbidden writes can be asserted absent at runtime. */
function recordApiPaths(page: Page): string[] {
  const paths: string[] = [];
  page.on('request', (request) => {
    if (request.url().startsWith(API)) paths.push(`${request.method()} ${new URL(request.url()).pathname}`);
  });
  return paths;
}

const FORBIDDEN_API = [
  /grade/i,
  /wrong[-_]?answer/i,
  /knowledge[-_]?points?\/.*progress/i,
  /knowledge[-_]?progress/i,
  /\/review/i,
  /\/ai-questions/i,
  /\/past-paper/i,
];

function watchApi(page: Page): RequestLog[] {
  const log: RequestLog[] = [];
  page.on('request', (request) => {
    if (!request.url().startsWith(API)) return;
    if (request.method() !== 'POST') return;
    try {
      log.push({ url: request.url(), body: request.postDataJSON(), response: null });
    } catch {
      log.push({ url: request.url(), body: null, response: null });
    }
  });
  page.on('response', async (response) => {
    if (!response.url().startsWith(API)) return;
    const entry = log.find((candidate) => candidate.url === response.url() && candidate.response === null);
    if (!entry) return;
    try {
      entry.response = await response.json();
    } catch {
      entry.response = null;
    }
  });
  return log;
}

async function login(page: Page) {
  const response = await page.request.post(`${API}/login`, { data: { username: USERNAME, password: PASSWORD } });
  expect(response.status(), 'real POST /login').toBe(200);
  const body = await response.json();
  expect(body.user.username).toBe(USERNAME);
  const cookies = await page.context().cookies(API);
  expect(cookies.map((cookie) => cookie.name)).toContain('ai_session');
  return cookies;
}

async function openDesk(page: Page) {
  await page.goto(PRACTICE);
  await expect(page.getByRole('heading', { name: '数据结构' })).toBeVisible();
  await expect(page.getByRole('radio', { name: CORRECT_OPTION })).toBeVisible();
}

async function createAndSubmit(page: Page, option: RegExp, bigAnswer = '先判断表满，再把元素后移，最后插入并加一。') {
  // answer both questions, then start the attempt and submit once — the real lifecycle.
  // Navigation uses 上一题 / 下一题, which is the only affordance available at both viewports
  // (the numbered navigator is intentionally hidden below 40rem).
  await page.getByRole('radio', { name: option }).check();
  await page.getByRole('button', { name: '下一题' }).click();
  await page.getByLabel('你的作答').fill(bigAnswer);
  await page.getByRole('button', { name: '上一题' }).click();
  await page.getByRole('button', { name: '开始本章练习' }).click();
  await page.getByRole('button', { name: '提交本章答案' }).click();
  await expect(page.locator('.practice-result, .practice-result--review')).toBeVisible();
}

test.beforeAll(() => {
  fs.mkdirSync(SCREENSHOTS, { recursive: true });
  setDouble('success');
});

test.describe.configure({ mode: 'serial' });

test.describe('F1C2C real backend VQA', () => {
  test('desktop: real choice correct feedback, AI explain, reload and big self-review', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    const api = watchApi(page);
    const apiPaths = recordApiPaths(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await openDesk(page);

    // the pre-submit question transport must not carry the answer or the explanation
    const preSubmitQuestions = await page.request.get(
      `${API}/exam/11408/data_structure/chapter-practice/questions?chapter_code=1`);
    const preSubmitItems = (await preSubmitQuestions.json()).items as Array<Record<string, unknown>>;
    expect(preSubmitItems.length).toBeGreaterThan(0);
    for (const item of preSubmitItems) {
      expect(item, 'pre-submit question leaks standard_answer').not.toHaveProperty('standard_answer');
      expect(item, 'pre-submit question leaks analysis').not.toHaveProperty('analysis');
    }

    await createAndSubmit(page, CORRECT_OPTION);

    await expect(page.getByText('回答正确')).toBeVisible();
    await expect(page.getByText('你的答案：B')).toBeVisible();
    await expect(page.getByText('正确答案：B')).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-choice-correct-feedback.png') });

    const beforeExplain = doubleCalls().length;
    await page.getByRole('button', { name: 'AI 讲解' }).click();
    await expect(page.getByText(EXPLAIN_TEXT)).toBeVisible();
    await expect(page.locator('.practice-result__ai')).not.toContainText('deepseek');
    await expect(page.locator('.practice-result__ai')).not.toContainText('request_id');
    await expect(page.locator('.practice-result__ai')).not.toContainText('vqa-double');
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-choice-ai-explain.png') });

    // exactly one provider call, and it went through the real route with post-submit authority
    expect(doubleCalls().length - beforeExplain).toBe(1);
    const explainRequest = api.find((entry) => entry.url.endsWith('/question-analysis'));
    expect(explainRequest, 'real POST /question-analysis').toBeTruthy();
    expect(explainRequest!.body).toMatchObject({
      standard_answer: 'B',
      user_answer: 'B',
      question_type: 'choice',
    });
    expect(explainRequest!.body!.stem).toContain('线性表的逻辑顺序');
    await expect(page.getByRole('button', { name: 'AI 讲解' })).toHaveCount(0);

    // no auto-retry after the successful response settled
    const settledCalls = doubleCalls().length;
    await page.waitForTimeout(1500);
    expect(doubleCalls().length).toBe(settledCalls);

    await page.reload();
    await expect(page.getByText('回答正确')).toBeVisible();
    await expect(page.getByText('你的答案：B')).toBeVisible();
    await expect(page.getByText('正确答案：B')).toBeVisible();
    await expect(page.getByText(EXPLAIN_TEXT)).toHaveCount(0); // AI output returns to idle on reload

    // post-reload the AI input is sourced from the REPLAYED submitted detail, still answer-owned
    api.length = 0;
    await page.getByRole('button', { name: 'AI 讲解' }).click();
    await expect(page.getByText(EXPLAIN_TEXT)).toBeVisible();
    const replayedExplain = api.find((entry) => entry.url.endsWith('/question-analysis'));
    expect(replayedExplain, 'real POST /question-analysis after reload').toBeTruthy();
    expect(replayedExplain!.body).toMatchObject({ standard_answer: 'B', user_answer: 'B', question_type: 'choice' });

    await page.getByRole('button', { name: '第 2 题' }).click();
    await expect(page.getByRole('heading', { name: '自行复盘' })).toBeVisible();
    const review = page.locator('.practice-result--review');
    await expect(review.getByText('你的作答')).toBeVisible();
    await expect(review.getByText('参考答案')).toBeVisible();
    await expect(review).toContainText('先判断表满');
    await expect(page.getByText('回答正确')).toHaveCount(0);
    await expect(page.getByText('回答错误')).toHaveCount(0);
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-big-self-review.png') });

    // runtime proof: the whole flow touched no grading, wrong-record or knowledge-status endpoint
    const forbidden = apiPaths.filter((entry) => FORBIDDEN_API.some((pattern) => pattern.test(entry)));
    expect(forbidden, `forbidden writes: ${forbidden.join(', ')}`).toEqual([]);
    expect(apiPaths.some((entry) => entry.includes('/question-analysis'))).toBe(true);
    expect(apiPaths.some((entry) => entry.includes('/chapter-practice/attempts'))).toBe(true);

    expect(errors).toEqual([]);
  });

  test('desktop: real choice incorrect feedback survives reload', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await openDesk(page);
    await createAndSubmit(page, WRONG_OPTION);

    await expect(page.getByText('回答错误')).toBeVisible();
    await expect(page.getByText('你的答案：A')).toBeVisible();
    await expect(page.getByText('正确答案：B')).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-choice-incorrect-feedback.png') });

    await page.reload();
    await expect(page.getByText('回答错误')).toBeVisible();
    await expect(page.getByText('你的答案：A')).toBeVisible();
    await expect(page.getByText('正确答案：B')).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('desktop: real AI provider failure is isolated from the grading result', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => {
      // the explicit controlled 502 probe is expected network noise, not an unhandled app error
      if (message.type() === 'error' && !message.text().includes('Failed to load resource')) errors.push(message.text());
    });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await openDesk(page);
    await createAndSubmit(page, CORRECT_OPTION);

    setDouble('raise_auth');
    const before = doubleCalls().length;
    await page.getByRole('button', { name: 'AI 讲解' }).click();
    await expect(page.getByRole('alert')).toHaveText('AI 讲解暂时不可用');
    await expect(page.getByRole('button', { name: '重新生成讲解' })).toBeVisible();

    // the grading result, the answer and the navigation all survive the AI failure
    await expect(page.getByText('回答正确')).toBeVisible();
    await expect(page.getByText('你的答案：B')).toBeVisible();
    await expect(page.getByText('正确答案：B')).toBeVisible();
    await expect(page.getByRole('button', { name: '第 2 题' })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-ai-failure.png') });

    // a failed non-retriable provider call is never retried automatically
    await page.waitForTimeout(2000);
    expect(doubleCalls().length - before).toBe(1);
    expect(doubleCalls().at(-1)!.behavior).toBe('raise_auth');

    // a big question keeps its static analysis through the same failure
    await page.getByRole('button', { name: '第 2 题' }).click();
    await expect(page.getByText(BIG_STATIC_ANALYSIS)).toBeVisible();
    await expect(page.getByRole('heading', { name: '自行复盘' })).toBeVisible();
    await page.getByRole('button', { name: 'AI 讲解' }).click();
    await expect(page.getByRole('alert')).toHaveText('AI 讲解暂时不可用');
    await expect(page.getByText(BIG_STATIC_ANALYSIS)).toBeVisible();
    await expect(page.locator('.practice-result--review').getByText('参考答案')).toBeVisible();
    setDouble('success');
    expect(errors).toEqual([]);
  });

  test('desktop: an in-flight AI explanation never bleeds into another question', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await openDesk(page);
    await createAndSubmit(page, CORRECT_OPTION);

    setDouble('success', 2500, '仅属于第 1 题的讲解内容。');
    const before = doubleCalls().length;
    await page.getByRole('button', { name: 'AI 讲解' }).click();
    await page.getByRole('button', { name: '第 2 题' }).click();
    await expect(page.getByRole('heading', { name: '自行复盘' })).toBeVisible();
    await expect(page.getByText('仅属于第 1 题的讲解内容。')).toHaveCount(0);
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-question-switch.png') });

    // let question A's response land while question B is on screen
    await expect.poll(() => doubleCalls().length, { timeout: 15000 }).toBe(before + 1);
    await page.waitForTimeout(1000);
    await expect(page.getByText('仅属于第 1 题的讲解内容。')).toHaveCount(0);

    await page.getByRole('button', { name: '第 1 题' }).click();
    await expect(page.getByText('仅属于第 1 题的讲解内容。')).toBeVisible();
    setDouble('success');
  });

  test('mobile: real feedback and AI explain with no scoped Axe violations', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await openDesk(page);
    await createAndSubmit(page, CORRECT_OPTION);

    await expect(page.getByText('回答正确')).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-choice-feedback.png') });

    await page.getByRole('button', { name: 'AI 讲解' }).click();
    await expect(page.getByText(EXPLAIN_TEXT)).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-ai-explain.png') });

    const results = await new AxeBuilder({ page }).include('.cs408-practice').analyze();
    expect(results.violations).toEqual([]);
    expect(errors).toEqual([]);
  });
});
