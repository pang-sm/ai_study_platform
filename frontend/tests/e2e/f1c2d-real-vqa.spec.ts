/**
 * F1C2D — REAL AUTHENTICATED BACKEND VQA (practice session summary).
 *
 * Runs against the real FastAPI app on port 8952 backed by a disposable TEMP database, with a real
 * `POST /login` session. Nothing is intercepted: the desk, the attempt, the submit, the summary and
 * the retry all go through the real endpoints.
 *
 * The expected summary is computed INDEPENDENTLY here, from the raw authoritative results fetched
 * over the API — never from the component's own helper — so the comparison cannot be
 * self-confirming.
 */
import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const API = 'http://127.0.0.1:8952';
const ROOT = path.join(process.env.TEMP ?? '.', 'f1c2d-real');
const SCREENSHOTS = path.join(ROOT, 'screenshots');
const CALLS = path.join(ROOT, 'double_calls.jsonl');
const USERNAME = 'f1c2d_student';
const PASSWORD = 'f1c2d-secret-123';
const PRACTICE = '/exam/cs408/practice?module=data_structure&chapter=1';

const CORRECT_CHOICE = /元素之间的前后关系/;   // question 1, standard "B"
const WRONG_CHOICE = /0 个/;                   // question 2 option A, standard is C -> wrong on purpose
const Q2_CORRECT = /约 n\/2 个/;
const Q3_CORRECT = /O\(n\)/;
const BIG_ANSWER = '先判断表满，再把元素后移，最后写入并加一。';

type RawResult = {
  question_id: number;
  question_type: 'choice' | 'big';
  user_answer: string;
  correct?: boolean | null;
  judge?: string;
  standard_answer: string;
};

/** Independent re-implementation of the frozen classification — deliberately NOT the app helper. */
function classify(results: RawResult[]) {
  const answered = results.filter((r) => r.user_answer !== '');
  const answeredChoices = answered.filter((r) => r.question_type === 'choice');
  const correct = answeredChoices.filter((r) => r.correct === true);
  const incorrect = answeredChoices.filter((r) => r.correct === false);
  const selfReview = answered.filter((r) => r.question_type === 'big' && r.judge === 'self_review');
  const denominator = correct.length + incorrect.length;
  return {
    total: results.length,
    answered: answered.length,
    unanswered: results.length - answered.length,
    correct: correct.length,
    incorrect: incorrect.length,
    selfReview: selfReview.length,
    retryIds: incorrect.map((r) => r.question_id).sort((a, b) => a - b),
    denominator,
    accuracyPercent: denominator ? Math.round((correct.length / denominator) * 100) : null,
  };
}

function doubleCalls(): Array<Record<string, unknown>> {
  if (!fs.existsSync(CALLS)) return [];
  return fs.readFileSync(CALLS, 'utf-8').trim().split('\n').filter(Boolean).map((line) => JSON.parse(line));
}

async function login(page: Page) {
  const response = await page.request.post(`${API}/login`, { data: { username: USERNAME, password: PASSWORD } });
  expect(response.status(), 'real POST /login').toBe(200);
  const cookies = await page.context().cookies(API);
  expect(cookies.map((cookie) => cookie.name)).toContain('ai_session');
}

async function rawResults(page: Page, attemptId: number): Promise<RawResult[]> {
  const response = await page.request.get(`${API}/exam/11408/data_structure/chapter-practice/attempts/${attemptId}`);
  expect(response.status()).toBe(200);
  return (await response.json()).results as RawResult[];
}

function attemptIdFromUrl(page: Page): number {
  const raw = new URL(page.url()).searchParams.get('attempt');
  expect(raw, `attempt id missing from ${page.url()}`).not.toBeNull();
  return Number(raw);
}

/** Create the mixed attempt through the real UI: correct choice, wrong choice, blank, answered big. */
async function startMixedAttempt(page: Page) {
  await page.goto(PRACTICE);
  await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeVisible();

  await page.getByRole('radio', { name: CORRECT_CHOICE }).check();   // Q1 correct
  await page.getByRole('button', { name: '下一题' }).click();
  await page.getByRole('radio', { name: WRONG_CHOICE }).check();     // Q2 incorrect
  await page.getByRole('button', { name: '下一题' }).click();        // Q3 left blank
  await page.getByRole('button', { name: '下一题' }).click();
  await page.getByLabel('你的作答').fill(BIG_ANSWER);                 // Q4 answered big
  await page.getByRole('button', { name: '开始本章练习' }).click();
  await expect(page.getByRole('button', { name: '提交本章答案' })).toBeVisible();
}

async function confirmAndSubmit(page: Page) {
  await page.getByRole('button', { name: '提交本章答案' }).click();
  await expect(page.getByRole('alertdialog')).toContainText('还有 1 题未作答');
  await page.getByRole('button', { name: '仍然提交' }).click();
  await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
}

/** The desk keeps the last-viewed index, so step back to question 1 with the shared affordance. */
async function gotoFirstQuestion(page: Page) {
  for (let i = 0; i < 8; i += 1) {
    if (await page.getByRole('radio', { name: CORRECT_CHOICE }).isVisible().catch(() => false)) return;
    const prev = page.getByRole('button', { name: '上一题' });
    if (!(await prev.isVisible().catch(() => false))) return;
    await prev.click();
    await page.waitForTimeout(80);
  }
}

test.beforeAll(() => fs.mkdirSync(SCREENSHOTS, { recursive: true }));

test.describe.configure({ mode: 'default' });

test.describe('F1C2D real backend VQA', () => {
  test('A/B/D — unanswered confirmation, mixed summary from authoritative results, and refresh', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    const createBodies: Array<Record<string, unknown>> = [];
    page.on('request', (request) => {
      if (request.method() === 'POST' && request.url().endsWith('/chapter-practice/attempts')) {
        try { createBodies.push(request.postDataJSON()); } catch { /* ignore */ }
      }
    });
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);

    // A — ordinary navigation never raises the confirmation
    await page.getByRole('button', { name: '上一题' }).click();
    await expect(page.getByRole('alertdialog')).toHaveCount(0);
    await expect(page.getByRole('button', { name: '继续作答' })).toHaveCount(0);
    await page.getByRole('button', { name: '下一题' }).click();
    await expect(page.getByRole('alertdialog')).toHaveCount(0);

    await page.getByRole('button', { name: '提交本章答案' }).click();
    await expect(page.getByRole('alertdialog')).toContainText('还有 1 题未作答');
    await expect(page.getByRole('button', { name: '继续作答' })).toBeVisible();
    await expect(page.getByRole('button', { name: '仍然提交' })).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-practice-submit-unanswered-confirm.png') });

    // 继续作答 dismisses without submitting
    await page.getByRole('button', { name: '继续作答' }).click();
    await expect(page.getByRole('alertdialog')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toHaveCount(0);

    await page.getByRole('button', { name: '提交本章答案' }).click();
    await page.getByRole('button', { name: '仍然提交' }).click();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();

    const attemptId = attemptIdFromUrl(page);
    const attempt = createBodies.at(-1);
    expect(attempt, 'real attempt create body').toBeTruthy();
    expect(Array.isArray(attempt!.question_ids)).toBe(true);

    // B — independent expectation from the raw authoritative results
    const raw = await rawResults(page, attemptId);
    const expected = classify(raw);
    expect(expected).toMatchObject({
      total: 4, answered: 3, unanswered: 1,
      correct: 1, incorrect: 1, selfReview: 1, denominator: 2, accuracyPercent: 50,
    });
    expect(expected.answered, 'answered = correct + incorrect + selfReview')
      .toBe(expected.correct + expected.incorrect + expected.selfReview);

    const summary = page.locator('.practice-summary');
    await expect(summary.getByText('共 4 题')).toBeVisible();
    await expect(summary.getByText(`已作答 ${expected.answered} · 答对 ${expected.correct} · 答错 ${expected.incorrect} · 自行复盘 ${expected.selfReview} · 未作答 ${expected.unanswered}`)).toBeVisible();
    await expect(summary.getByText(`自动判分题正确率 ${expected.accuracyPercent}%`)).toBeVisible();
    // the blank question is counted as unanswered, never folded into 答错
    await expect(summary).not.toContainText(`答错 ${expected.incorrect + expected.unanswered}`);
    await expect(summary).toContainText(`答错 ${expected.incorrect} `);
    await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-practice-session-summary-mixed.png') });

    // D — browser refresh replays the same summary from the submitted attempt detail
    await page.reload();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
    await expect(page.locator('.practice-summary').getByText(`已作答 ${expected.answered} · 答对 ${expected.correct} · 答错 ${expected.incorrect} · 自行复盘 ${expected.selfReview} · 未作答 ${expected.unanswered}`)).toBeVisible();
    await expect(page.locator('.practice-summary').getByText(`自动判分题正确率 ${expected.accuracyPercent}%`)).toBeVisible();

    expect(doubleCalls()).toEqual([]);   // no AI call anywhere in the summary lifecycle
    expect(errors).toEqual([]);
  });

  test('C — submitted replay defaults to summary and supports read-only question review', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    await confirmAndSubmit(page);

    await page.getByRole('button', { name: '查看本次题目' }).click();
    await expect(page.locator('.practice-question')).toBeVisible();
    // the desk resumes at the last-viewed question, so step to q1 before asserting its answer
    await page.getByRole('button', { name: '第 1 题' }).click();
    await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeChecked();
    await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeDisabled();
    await expect(page.getByText('回答正确')).toBeVisible();
    // the big question's submitted text is restored from the authoritative result and locked
    await page.getByRole('button', { name: '第 4 题' }).click();
    const restoredBig = page.getByLabel('你的作答');
    await expect(restoredBig).toHaveValue(BIG_ANSWER);
    await expect(restoredBig).toBeDisabled();
    await page.getByRole('button', { name: '本次练习总结' }).click();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();

    await page.reload();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
    await page.getByRole('button', { name: '查看本次题目' }).click();
    await expect(page.locator('.practice-question')).toBeVisible();

    await page.getByRole('button', { name: '第 1 题' }).click();
    await expect(page.locator('.practice-question')).toBeVisible();
    await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeChecked();
  });

  test('E — 重练本次错题 creates a new attempt holding only the answered incorrect choice', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    await confirmAndSubmit(page);

    const originalId = attemptIdFromUrl(page);
    const expected = classify(await rawResults(page, originalId));
    expect(expected.retryIds).toHaveLength(1);

    await page.getByRole('button', { name: '重练本次错题' }).click();
    await expect.poll(() => attemptIdFromUrl(page)).not.toBe(originalId);
    const newId = attemptIdFromUrl(page);

    const body = await (await page.request.get(`${API}/exam/11408/data_structure/chapter-practice/attempts/${newId}`)).json();
    const newQuestionIds: number[] = (body.questions as Array<{ id: number }>).map((q) => q.id).sort((a, b) => a - b);

    // exactly the incorrect choice: blank absent, big absent, correct choice absent
    const wrongId = (await rawResults(page, originalId)).find((r) => r.correct === false)!.question_id;
    expect(newQuestionIds).toEqual([wrongId]);
    expect(newQuestionIds).toEqual(expected.retryIds);
    expect(body.attempt.status).toBe('in_progress');

    // the original attempt is untouched
    const original = await (await page.request.get(`${API}/exam/11408/data_structure/chapter-practice/attempts/${originalId}`)).json();
    expect(original.attempt.status).toBe('submitted');
    expect(original.results).toHaveLength(4);

    const renderedQuestionIds = await page.locator('.practice-question input, .practice-question textarea').evaluateAll((controls) => controls.map((control) => Number(control.id.replace('answer-', '') || control.getAttribute('name')?.replace('question-', ''))));
    await expect(page.getByRole('button', { name: '第 1 题' })).toHaveCount(1);
    await expect(page.getByRole('button', { name: '第 2 题' })).toHaveCount(0);
    expect([...new Set(renderedQuestionIds)]).toEqual([wrongId]);

    await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-practice-retry-incorrect.png') });
  });

  test('F — 再做一遍本章 starts a fresh full-chapter attempt and keeps the old one intact', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    await confirmAndSubmit(page);

    const originalId = attemptIdFromUrl(page);
    const chapterQuestionIds = (await rawResults(page, originalId)).map((r) => r.question_id).sort((a, b) => a - b);

    await page.getByRole('button', { name: '再做一遍本章' }).click();
    await expect.poll(() => attemptIdFromUrl(page)).not.toBe(originalId);
    const newId = attemptIdFromUrl(page);
    expect(newId).not.toBe(originalId);

    const body = await (await page.request.get(`${API}/exam/11408/data_structure/chapter-practice/attempts/${newId}`)).json();
    const ids: number[] = (body.questions as Array<{ id: number }>).map((q) => q.id).sort((a, b) => a - b);
    expect(ids).toEqual(chapterQuestionIds);
    expect(body.attempt.status).toBe('in_progress');

    // a genuinely fresh answering session on the real chapter question set
    await gotoFirstQuestion(page);
    await expect(page.getByRole('radio', { name: CORRECT_CHOICE })).toBeEnabled();
    await expect(page.getByRole('button', { name: '提交本章答案' })).toBeVisible();

    // the previous attempt stays submitted and intact
    const original = await (await page.request.get(`${API}/exam/11408/data_structure/chapter-practice/attempts/${originalId}`)).json();
    expect(original.attempt.status).toBe('submitted');
    expect(original.results).toHaveLength(4);
  });

  test('G — 返回章节 keeps the canonical module/chapter context', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    await confirmAndSubmit(page);

    await page.getByRole('link', { name: '返回章节' }).click();
    await expect(page.getByRole('heading', { name: '章节目录' })).toBeVisible();
    const params = new URL(page.url()).searchParams;
    expect(params.get('module')).toBe('data_structure');
    expect(params.get('chapter')).toBeNull();

    // the chapter link carries the canonical chapter_code, not an index or a Chinese title
    await page.getByRole('link', { name: /第 1 章/ }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get('chapter')).toBe('1');
    expect(new URL(page.url()).searchParams.get('module')).toBe('data_structure');
  });

  test('H — summary and confirmation meet scoped Axe checks', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);
    await startMixedAttempt(page);

    await page.getByRole('button', { name: '提交本章答案' }).click();
    await expect(page.getByRole('alertdialog')).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'mobile-practice-unanswered-confirm.png') });

    await page.getByRole('button', { name: '仍然提交' }).click();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();
    const expected = classify(await rawResults(page, attemptIdFromUrl(page)));
    await expect(page.locator('.practice-summary').getByText(`已作答 ${expected.answered} · 答对 ${expected.correct} · 答错 ${expected.incorrect} · 自行复盘 ${expected.selfReview} · 未作答 ${expected.unanswered}`)).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'mobile-practice-session-summary.png') });

    expect(errors).toEqual([]);
    expect((await new AxeBuilder({ page }).include('.cs408-practice').analyze()).violations).toEqual([]);
  });

  test('I — the desktop summary and answered navigator meet scoped Axe checks', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    await confirmAndSubmit(page);

    const results = await new AxeBuilder({ page }).include('.cs408-practice').analyze();
    const contrast = results.violations.filter((entry) => entry.id === 'color-contrast');
    const targets = contrast.flatMap((entry) => entry.nodes.map((node) => node.target.join(' ')));
    console.log(`[desktop axe] ${targets.join(' | ')}`);

    expect(targets).toEqual([]);
    expect(results.violations).toEqual([]);
  });

  // §8 — with no auto-graded question the summary must not print a fake 0%.
  test('J — a session with no auto-graded question never shows a fake 0%', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);

    const questionsBody = await (await page.request.get(
      `${API}/exam/11408/data_structure/chapter-practice/questions?chapter_code=1`)).json();
    const bigId = (questionsBody.items as Array<{ id: number; question_type: string }>)
      .find((q) => q.question_type === 'big')!.id;

    const created = await page.request.post(
      `${API}/exam/11408/data_structure/chapter-practice/attempts`, { data: { question_ids: [bigId] } });
    const attemptId = (await created.json()).attempt_id;
    const submitted = await page.request.post(
      `${API}/exam/11408/data_structure/chapter-practice/attempts/${attemptId}/submit`,
      { data: { answers: { [String(bigId)]: BIG_ANSWER } } });
    expect(submitted.status()).toBe(200);

    await page.goto(`/exam/cs408/practice?module=data_structure&chapter=1&attempt=${attemptId}`);
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();

    const summary = page.locator('.practice-summary');
    await expect(summary.getByText('本次没有自动判分题')).toBeVisible();
    await expect(summary).not.toContainText('正确率');
    await expect(summary).toContainText('自行复盘 1');
    await expect(summary).toContainText('答错 0');
  });

  test('desktop full summary (every question answered) stays an exam sheet, not a dashboard', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await login(page);
    await startMixedAttempt(page);
    await confirmAndSubmit(page);
    const attemptId = attemptIdFromUrl(page);

    // repeat the chapter and answer everything, so the summary has no unanswered row
    await page.getByRole('button', { name: '再做一遍本章' }).click();
    await expect.poll(() => attemptIdFromUrl(page)).not.toBe(attemptId);
    await gotoFirstQuestion(page);
    await page.getByRole('radio', { name: CORRECT_CHOICE }).check();
    await page.getByRole('button', { name: '下一题' }).click();
    await page.getByRole('radio', { name: Q2_CORRECT }).check();
    await page.getByRole('button', { name: '下一题' }).click();
    await page.getByRole('radio', { name: Q3_CORRECT }).check();
    await page.getByRole('button', { name: '下一题' }).click();
    await page.getByLabel('你的作答').fill(BIG_ANSWER);
    await page.getByRole('button', { name: '提交本章答案' }).click();
    await expect(page.getByRole('heading', { name: '本次练习完成' })).toBeVisible();

    const expected = classify(await rawResults(page, attemptIdFromUrl(page)));
    expect(expected.unanswered).toBe(0);
    expect(expected.accuracyPercent).toBe(100);
    await expect(page.locator('.practice-summary').getByText(`已作答 ${expected.answered} · 答对 ${expected.correct} · 答错 ${expected.incorrect} · 自行复盘 ${expected.selfReview} · 未作答 ${expected.unanswered}`)).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-practice-session-summary.png') });
  });
});

