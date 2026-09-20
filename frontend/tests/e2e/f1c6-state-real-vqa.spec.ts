import fs from 'node:fs';
import path from 'node:path';
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const API = process.env.ACCEL_VQA_API ?? 'http://127.0.0.1:8972';
const SCREENSHOTS = path.resolve('.f1c6tmp', 'screenshots');
const USER = { username: 'f1c6_state_student', password: 'f1c6-state-secret-123' };

async function ensureUser(request: APIRequestContext) {
  const login = await request.post(`${API}/login`, { data: USER });
  expect(login.status(), 'real POST /login').toBe(200);
}

async function answerChapter(request: APIRequestContext) {
  const questions = await (await request.get(`${API}/exam/11408/data_structure/chapter-practice/questions?chapter_code=1`)).json() as { items: Array<{ id: number; question_type: string; standard_answer?: string }> };
  const question = questions.items.find((item) => item.question_type === 'choice');
  expect(question, 'a real data-structure choice question').toBeTruthy();
  const start = await request.post(`${API}/exam/11408/data_structure/chapter-practice/attempts`, { data: { question_ids: [question!.id] } });
  expect(start.status()).toBe(200);
  const { attempt_id } = await start.json() as { attempt_id: number };
  const submit = await request.post(`${API}/exam/11408/data_structure/chapter-practice/attempts/${attempt_id}/submit`, { data: { answers: { [question!.id]: 'A' } } });
  expect(submit.status()).toBe(200);
}

async function answerPastPaper(request: APIRequestContext) {
  const questions = await (await request.get(`${API}/exam/11408/operating_system/past-paper-questions?year=2022`)).json() as { questions: Array<{ question_number: number; question_type: string }> };
  const question = questions.questions.find((item) => item.question_type === 'choice');
  expect(question, 'a real OS past-paper choice question').toBeTruthy();
  const start = await request.post(`${API}/exam/11408/operating_system/past-paper-attempts`, { data: { year: 2022 } });
  expect(start.status()).toBe(200);
  const { attempt_id } = await start.json() as { attempt_id: number };
  const submit = await request.post(`${API}/exam/11408/operating_system/past-paper-attempts/${attempt_id}/submit`, { data: { answers: { [question!.question_number]: 'A' } } });
  expect(submit.status()).toBe(200);
}

function trackProblems(page: Page) {
  const errors: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', (error) => errors.push(error.message));
  return errors;
}

test.beforeAll(() => fs.mkdirSync(SCREENSHOTS, { recursive: true }));
test.describe.configure({ mode: 'serial' });

test('records are factual, cursor-paginated, filtered server-side and accessible', async ({ page, request }) => {
  await ensureUser(request);
  for (let index = 0; index < 30; index += 1) await answerChapter(request);
  await answerPastPaper(request);
  const first = await request.get(`${API}/exam/prep/records?limit=30`);
  expect(first.status()).toBe(200);
  const firstPage = await first.json() as { records: Array<{ event_type: string; context?: { exam_module_id?: string | null } }>; has_more: boolean; next_cursor: string | null };
  expect(firstPage.records).toHaveLength(30);
  expect(firstPage.has_more).toBe(true);
  expect(firstPage.next_cursor).toBeTruthy();
  expect(firstPage.records.some((item) => item.event_type === 'ai_called')).toBe(false);
  const second = await request.get(`${API}/exam/prep/records?limit=30&cursor=${encodeURIComponent(firstPage.next_cursor!)}`);
  const secondPage = await second.json() as { records: unknown[] };
  expect(secondPage.records.length).toBeGreaterThan(0);

  const errors = trackProblems(page);
  const traffic: Array<{ method: string; url: string }> = [];
  page.on('request', (request) => traffic.push({ method: request.method(), url: request.url() }));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.request.post(`${API}/login`, { data: USER });
  await page.goto('/exam/cs408/records');
  await expect(page.getByRole('heading', { name: '学习记录档案' })).toBeVisible();
  await expect(page.locator('.learning-records__row')).toHaveCount(30);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-records.png'), fullPage: true });
  await page.getByRole('button', { name: '加载更多' }).click();
  await expect(page.locator('.learning-records__row')).toHaveCount(firstPage.records.length + secondPage.records.length);
  await page.getByRole('link', { name: '操作系统' }).click();
  await expect(page).toHaveURL(/\/exam\/cs408\/records\?module=operating_system/);
  const filtered = await request.get(`${API}/exam/prep/records?exam_module_id=operating_system&limit=30`);
  const filteredPage = await filtered.json() as { records: unknown[] };
  await expect(page.locator('.learning-records__row')).toHaveCount(filteredPage.records.length);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-records-filtered.png'), fullPage: true });
  expect(traffic.filter((item) => item.url.includes('/exam/prep/records')).every((item) => item.method === 'GET')).toBe(true);
  const forbiddenTraffic = traffic.filter((item) => item.url.startsWith(API) && /learning-records|wrong-answers|learning\/tasks/.test(item.url));
  expect(forbiddenTraffic, JSON.stringify(forbiddenTraffic)).toEqual([]);
  expect(await new AxeBuilder({ page }).include('.learning-records').analyze()).toMatchObject({ violations: [] });
  expect(errors).toEqual([]);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/exam/cs408/records');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'mobile-records.png'), fullPage: true });
});

test('student twin preview is a real read-only experiment with module scope', async ({ page, request }) => {
  await ensureUser(request);
  await answerChapter(request);
  const preview = await request.get(`${API}/exam/prep/scientific/student-twin?exam_module_id=data_structure`);
  expect(preview.status()).toBe(200);
  const response = await preview.json() as { metadata: { mode: string; writes_learner_fact: boolean; controls_product_decision: boolean; blockers?: string[] }; input_summary: { event_count: number } };
  expect(response.metadata.mode).toBe('PREVIEW');
  expect(response.metadata.writes_learner_fact).toBe(false);
  expect(response.metadata.controls_product_decision).toBe(false);
  expect(response.input_summary.event_count).toBeGreaterThan(0);
  expect(response.metadata.blockers ?? []).not.toContain('INPUT_FAMILY_NOT_STUDENT_TWIN_ELIGIBLE');

  const errors = trackProblems(page);
  const traffic: Array<{ method: string; url: string }> = [];
  page.on('request', (request) => traffic.push({ method: request.method(), url: request.url() }));
  await page.request.post(`${API}/login`, { data: USER });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/exam/cs408/state');
  await expect(page.getByRole('heading', { name: '学习状态实验视图' })).toBeVisible();
  await expect(page.getByText('自研确定性学习状态引擎')).toBeVisible();
  await expect(page.getByText('基于真实作答与学习事件')).toBeVisible();
  await expect(page.getByText('本次计算使用的 factual evidence')).toBeVisible();
  await expect(page.getByText(/不控制判分，不修改知识状态、错题或学习计划/)).toBeVisible();
  await expect(page.getByText(/learner_state|misconception_v2|tutor_policy|evidence_reliability|SCIENTIFIC_RUNTIME_UNAVAILABLE/i)).toHaveCount(0);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-state.png'), fullPage: true });
  await page.getByRole('link', { name: '数据结构' }).click();
  await expect(page).toHaveURL(/\/exam\/cs408\/state\?module=data_structure/);
  await expect(page.getByText('当前学习状态摘要')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole('link', { name: '查看学习记录' })).toHaveAttribute('href', '/exam/cs408/records?module=data_structure');
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-state-module.png'), fullPage: true });
  expect(traffic.filter((item) => /scientific\/(capabilities|student-twin)/.test(item.url)).every((item) => item.method === 'GET')).toBe(true);
  expect(traffic.some((item) => item.url.includes('/exam/prep/scientific/capabilities') && item.method === 'GET')).toBe(true);
  expect(traffic.some((item) => item.method !== 'GET' && /knowledge|wrong|practice|past-paper|plan|student-twin/.test(item.url))).toBe(false);
  expect(await new AxeBuilder({ page }).include('.student-twin').analyze()).toMatchObject({ violations: [] });
  expect(errors).toEqual([]);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/exam/cs408/state?module=data_structure');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'mobile-state.png'), fullPage: true });
});

test('student twin unavailable is bounded while records remain usable', async ({ page, request }) => {
  await ensureUser(request);
  const errors = trackProblems(page);
  await page.request.post(`${API}/login`, { data: USER });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/exam/cs408/state');
  await expect(page.getByText('学习状态服务暂时不可用')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/SCIENTIFIC_RUNTIME_UNAVAILABLE/)).toHaveCount(0);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'desktop-state-unavailable.png'), fullPage: true });
  await page.goto('/exam/cs408/records');
  await expect(page.getByRole('heading', { name: '学习记录档案' })).toBeVisible();
  expect(errors).toEqual([]);
});
