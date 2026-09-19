import fs from 'node:fs';
import path from 'node:path';
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext } from '@playwright/test';

const API = 'http://127.0.0.1:8958';
const ROOT = path.join(process.env.TEMP ?? '.', 'f1c4-real');
const SCREENSHOTS = path.join(ROOT, 'screenshots');
const userA = { username: 'f1c4_student_a', password: 'f1c4-pass-123' };
const userB = { username: 'f1c4_student_b', password: 'f1c4-pass-123' };

type Choice = { id: number; question_type: string };
type Result = { question_id: number | string; number?: number; correct: boolean | null; standard_answer: string; user_answer: string };
type Wrong = { wrong_record_id: number; status: string; module_key: string; source_kind: string; year: number | null; question_number: number | null; user_answer: string };

async function login(request: APIRequestContext, user: typeof userA) {
  const response = await request.post(`${API}/login`, { data: user });
  expect(response.status()).toBe(200);
}

async function canonical(request: APIRequestContext, module?: string) {
  const query = new URLSearchParams({ service_namespace: 'exam_prep', limit: '50', offset: '0' });
  if (module) query.set('module', module);
  const response = await request.get(`${API}/wrong-answers?${query}`);
  expect(response.status()).toBe(200);
  return response.json() as Promise<{ items: Wrong[]; total: number }>;
}

async function createChapter(request: APIRequestContext, questionId: number, answer: string) {
  const created = await request.post(`${API}/exam/11408/data_structure/chapter-practice/attempts`, { data: { question_ids: [questionId] } });
  expect(created.status()).toBe(200);
  const { attempt_id } = await created.json() as { attempt_id: number };
  const submitted = await request.post(`${API}/exam/11408/data_structure/chapter-practice/attempts/${attempt_id}/submit`, { data: { answers: { [questionId]: answer } } });
  expect(submitted.status()).toBe(200);
  return (await submitted.json()).results[0] as Result;
}

async function createPastPaper(request: APIRequestContext, questionNumber: number, answer: string) {
  const created = await request.post(`${API}/exam/11408/operating_system/past-paper-attempts`, { data: { year: 2022 } });
  expect(created.status()).toBe(200);
  const { attempt_id } = await created.json() as { attempt_id: number };
  const submitted = await request.post(`${API}/exam/11408/operating_system/past-paper-attempts/${attempt_id}/submit`, { data: { answers: { [questionNumber]: answer } } });
  expect(submitted.status()).toBe(200);
  const body = await submitted.json() as { results: Result[] };
  return body.results.find((result) => String(result.question_id) === String(questionNumber)) ?? body.results[0]!;
}

function opposite(answer: string) { return answer === 'A' ? 'B' : 'A'; }

test.beforeAll(() => fs.mkdirSync(SCREENSHOTS, { recursive: true }));

test('canonical wrong ledger is factual, isolated, responsive and accessible', async ({ page }) => {
  const request = page.request;
  const errors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', (error) => errors.push(error.message));
  await login(request, userA);

  const chapterQuestions = await (await request.get(`${API}/exam/11408/data_structure/chapter-practice/questions?chapter_code=1`)).json() as { items: Choice[] };
  const choice = chapterQuestions.items.find((question) => question.question_type === 'choice')!;
  const big = chapterQuestions.items.find((question) => question.question_type === 'big')!;

  // An initial factual submission reveals the authoritative answer; the next submits are intentionally wrong.
  const first = await createChapter(request, choice.id, 'A');
  const wrongAnswer = opposite(first.standard_answer);
  if (first.correct === true) await createChapter(request, choice.id, wrongAnswer);
  await createChapter(request, choice.id, wrongAnswer);
  const active = await canonical(request, 'data_structure');
  const chapterWrong = active.items.find((item) => item.module_key === 'data_structure' && item.user_answer === wrongAnswer)!;
  expect(chapterWrong).toMatchObject({ status: 'active', source_kind: 'chapter_practice' });
  expect(chapterWrong.wrong_record_id).toEqual(expect.any(Number));

  // Blank and self-review submissions do not create canonical wrong state.
  await createChapter(request, choice.id, '');
  await createChapter(request, big.id, '主观题自行复盘');
  const afterBlankAndBig = await canonical(request, 'data_structure');
  expect(afterBlankAndBig.items).toHaveLength(active.items.length);
  expect(afterBlankAndBig.items.every((item) => item.user_answer !== '')).toBe(true);

  const paper = await (await request.get(`${API}/exam/11408/operating_system/past-paper-questions?year=2022`)).json() as { questions: Array<{ question_number: number; question_type: string }> };
  const paperChoice = paper.questions.find((question) => question.question_type === 'choice')!;
  const firstPaper = await createPastPaper(request, paperChoice.question_number, 'A');
  const paperWrongAnswer = opposite(firstPaper.standard_answer);
  if (firstPaper.correct === true) await createPastPaper(request, paperChoice.question_number, paperWrongAnswer);
  const paperWrongs = await canonical(request, 'operating_system');
  const paperWrong = paperWrongs.items.find((item) => item.source_kind === 'past_paper')!;
  expect(paperWrong).toMatchObject({ status: 'active', module_key: 'operating_system', year: 2022, question_number: paperChoice.question_number });
  expect((await canonical(request, 'computer_network')).items).toEqual([]);

  // Correct retry changes only the server-owned factual state.
  await createChapter(request, choice.id, first.standard_answer);
  const resolved = (await canonical(request, 'data_structure')).items.find((item) => item.wrong_record_id === chapterWrong.wrong_record_id)!;
  expect(resolved.status).toBe('resolved');

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/exam/cs408/wrong?status=all');
  await expect(page.getByRole('heading', { name: '错题档案' })).toBeVisible();
  await expect(page.locator('.wrong-answer__status', { hasText: '已订正' })).toBeVisible();
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-wrong-ledger-resolved.png') });
  await page.locator('.wrong-answer__row', { hasText: '章节练习' }).first().getByRole('button', { name: /展开第/ }).click();
  await expect(page.locator('.wrong-answer__detail')).toBeVisible();
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-wrong-detail-chapter.png') });
  await page.goto('/exam/cs408/wrong?module=operating_system&status=active');
  await expect(page.getByText('历年真题 · 2022')).toBeVisible();
  await expect(page.locator('.wrong-answer__status', { hasText: '未订正' })).toBeVisible();
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-wrong-ledger-active.png') });
  await page.getByRole('button', { name: /展开第/ }).first().click();
  await expect(page.getByRole('link', { name: '查看原真题' })).toBeVisible();
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-wrong-detail-past-paper.png') });
  expect((await new AxeBuilder({ page }).include('.wrong-answer').analyze()).violations).toEqual([]);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/exam/cs408/wrong?module=operating_system&status=active');
  await expect(page.locator('.wrong-answer__ledger')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'mobile-wrong-ledger.png') });
  await page.getByRole('button', { name: /展开第/ }).first().click();
  await page.screenshot({ path: path.join(SCREENSHOTS, 'mobile-wrong-detail.png') });

  // A separate authenticated user receives no state, while anonymous access is denied.
  const browser = page.context().browser()!;
  const anonymousContext = await browser.newContext();
  const anonymous = await anonymousContext.request.get(`${API}/wrong-answers?service_namespace=exam_prep`);
  expect(anonymous.status()).toBe(401);
  await anonymousContext.close();
  const other = await browser.newContext();
  await login(other.request, userB);
  expect((await canonical(other.request)).items).toEqual([]);
  await other.close();
  expect(errors).toEqual([]);
  expect((await canonical(request)).total).toBeGreaterThanOrEqual(2);
});
