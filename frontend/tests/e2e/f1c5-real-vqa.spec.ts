/**
 * F1C5 — REAL AUTHENTICATED BACKEND VQA (CS408 study-plan workspace).
 *
 * Runs against the real FastAPI app on port 8965 backed by a disposable TEMP database, with a
 * real `POST /login` session. Nothing is intercepted: the entitlement, the canonical plan
 * response and every derived status go through the real endpoints.
 *
 * The two authorization states are both exercised for real, because the workspace is a paid
 * surface by product policy:
 *   - f1c5_free  -> `learning_plan.allowed !== true` -> locked state, and NO plan request
 *   - f1c5_paid  -> allowed -> canonical ledger
 *
 * Factual actions (marking knowledge points learned) are issued from a SEPARATE API context,
 * never from the page, so the page's own request log stays a clean record of what the
 * FRONTEND did.
 */
import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const API = 'http://127.0.0.1:8965';
const ROOT = path.join('.f1c5qa', 'screenshots');
const SCREENSHOTS = path.resolve(ROOT);

const PASSWORD = 'f1c5-secret-123';
const FREE = { username: 'f1c5_free', password: PASSWORD };
const PAID = { username: 'f1c5_paid', password: PASSWORD };
const OTHER = { username: 'f1c5_other', password: PASSWORD };

const MODULE = 'operating_system';
const PLAN_PATH = '/exam/cs408/plan';
const PLAN_API = `/exam/11408/subjects/${MODULE}/study-plan`;

const KNOWLEDGE_TASK = '复习：操作系统的基本概念';
const PRACTICE_TASK = '章节练习：操作系统概述';
const OTHER_TASK = '别人的任务';

type PlanTask = {
  id: number; subject_key: string; title: string; task_type: string;
  computed_status: 'not_started' | 'in_progress' | 'completed';
  action_target: 'knowledge_map' | 'practice_center';
  knowledge_point_name: string; due_date: string;
};
type Plan = { chapters: Array<{ children?: Array<Record<string, unknown>> }>; tasks: PlanTask[] };
type Entitlement = { service_key: string; current_plan: string; features: Record<string, { allowed: boolean; required_plan: string }> };

const STATUS_TEXT: Record<PlanTask['computed_status'], string> = {
  not_started: '未开始', in_progress: '进行中', completed: '已完成',
};

async function apiLogin(request: APIRequestContext, user: { username: string; password: string }) {
  const response = await request.post(`${API}/login`, { data: user });
  expect(response.status(), `real POST /login for ${user.username}`).toBe(200);
}

async function readPlan(request: APIRequestContext): Promise<Plan> {
  const response = await request.get(`${API}${PLAN_API}`);
  expect(response.status()).toBe(200);
  return response.json() as Promise<Plan>;
}

async function readEntitlement(request: APIRequestContext): Promise<Entitlement> {
  const response = await request.get(`${API}/membership/entitlements?service_key=exam_11408`);
  expect(response.status()).toBe(200);
  return response.json() as Promise<Entitlement>;
}

/** The leaf codes the BACKEND counts for a section — read from its own response, not guessed. */
function sectionLeaves(plan: Plan, sectionTitle: string): string[] {
  const found: string[] = [];
  const walk = (node: Record<string, unknown>): void => {
    if (node['is_leaf'] === true && typeof node['code'] === 'string') found.push(node['code']);
    for (const child of (node['children'] as Array<Record<string, unknown>> | undefined) ?? []) walk(child);
  };
  for (const chapter of plan.chapters) {
    for (const section of chapter.children ?? []) {
      if (section['title'] === sectionTitle) walk(section);
    }
  }
  return found;
}

async function setKnowledge(request: APIRequestContext, codes: string[], status: 'mastered' | 'not_started') {
  for (const code of codes) {
    const response = await request.patch(`${API}/exam/11408/subjects/${MODULE}/study-plan/knowledge-items/${encodeURIComponent(code)}`,
      { data: { username: PAID.username, subject_key: MODULE, course_id: `${MODULE}_11408`, knowledge_point_code: code, status } });
    expect(response.status(), `set ${code} -> ${status}`).toBe(200);
  }
}

/** Browser-side network, recorded so the FRONTEND's own calls can be audited separately. */
function frontendTraffic(page: Page) {
  const requests: Array<{ method: string; url: string }> = [];
  page.on('request', (r) => requests.push({ method: r.method(), url: r.url() }));
  return requests;
}

function consoleProblems(page: Page) {
  const errors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(e.message));
  return errors;
}

async function loginAs(page: Page, user: { username: string; password: string }) {
  const response = await page.request.post(`${API}/login`, { data: user });
  expect(response.status()).toBe(200);
}

/** §18 — the mobile layout must not scroll sideways. */
async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const el = document.documentElement;
    const widest = Array.from(document.querySelectorAll('body *'))
      .map((n) => n.getBoundingClientRect().right)
      .reduce((a, b) => Math.max(a, b), 0);
    return { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth, widest };
  });
  expect(overflow.scrollWidth, `horizontal overflow: ${JSON.stringify(overflow)}`)
    .toBeLessThanOrEqual(overflow.clientWidth);
}

// These tests share one TEMP backend and one mutable learner state, and the completion test
// drives that state, so they must not interleave.
test.describe.configure({ mode: 'serial' });

test.beforeAll(() => fs.mkdirSync(SCREENSHOTS, { recursive: true }));

// ================================================================ §7 free / locked

test('free learner sees the locked state and the frontend never asks for the plan', async ({ page, request }) => {
  const errors = consoleProblems(page);
  const traffic = frontendTraffic(page);
  await apiLogin(request, FREE);
  const entitlement = await readEntitlement(request);
  expect(entitlement.features['learning_plan']?.allowed ?? false, 'free is denied learning_plan').toBe(false);

  await loginAs(page, FREE);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(PLAN_PATH);

  await expect(page.getByRole('heading', { name: '学习计划' })).toBeVisible();
  await expect(page.getByText('当前会员暂未开放学习计划')).toBeVisible();

  // the entitlement gate is real: no protected plan request may be issued
  const planCalls = traffic.filter((r) => r.url.includes('/study-plan'));
  expect(planCalls, `plan requests while denied: ${JSON.stringify(planCalls)}`).toEqual([]);
  expect(traffic.some((r) => r.url.includes('/membership/entitlements')), 'the gate itself was asked').toBe(true);

  await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-plan-locked.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-plan-locked.png'), fullPage: true });

  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  expect(errors).toEqual([]);
});

// ================================================================ §8/§10/§13/§14 paid

test('paid learner loads the canonical ledger with backend-derived statuses', async ({ page, request }) => {
  const errors = consoleProblems(page);
  const traffic = frontendTraffic(page);
  await apiLogin(request, PAID);
  const entitlement = await readEntitlement(request);
  expect(entitlement.features['learning_plan']?.allowed).toBe(true);
  const plan = await readPlan(request);

  await loginAs(page, PAID);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(PLAN_PATH);
  await expect(page.getByRole('heading', { name: '学习计划' })).toBeVisible();

  const ledger = page.locator('.study-plan__ledger');
  await expect(ledger).toBeVisible();
  await expect(page.locator('.study-plan__row')).toHaveCount(plan.tasks.length);

  // every row shows the status the BACKEND derived for that task — compared, not assumed
  for (const task of plan.tasks) {
    const row = page.locator('.study-plan__row').filter({ hasText: task.title });
    await expect(row).toHaveCount(1);
    await expect(row.locator('.study-plan__status')).toHaveText(STATUS_TEXT[task.computed_status]);
    await expect(row.locator('dd').first()).toHaveText(STATUS_TEXT[task.computed_status]);
  }

  // canonical plan API only; nothing from the generic learning-task system
  expect(traffic.filter((r) => r.url.includes('/learning/tasks'))).toEqual([]);
  expect(traffic.filter((r) => r.url.includes('/learning/plans'))).toEqual([]);
  expect(traffic.filter((r) => r.url.includes('/study-plan')).length).toBeGreaterThan(0);

  // §13 no today view, and a null start_date is never reconstructed
  const body = await page.locator('body').innerText();
  for (const forbidden of ['今天', '今日任务', '今日完成度', '1970', '本周']) {
    expect(body, `plan page must not show "${forbidden}"`).not.toContain(forbidden);
  }

  await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-plan-ledger.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expectNoHorizontalOverflow(page);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'real-mobile-plan-ledger.png'), fullPage: true });

  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  expect(errors).toEqual([]);
});

// ================================================================ §11 action_target

test('the task CTA navigates to the workspace the backend named', async ({ page, request }) => {
  const errors = consoleProblems(page);
  await apiLogin(request, PAID);
  const plan = await readPlan(request);
  const knowledge = plan.tasks.find((t) => t.title === KNOWLEDGE_TASK);
  const practice = plan.tasks.find((t) => t.title === PRACTICE_TASK);
  expect(knowledge?.action_target).toBe('knowledge_map');
  expect(practice?.action_target).toBe('practice_center');

  await loginAs(page, PAID);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(PLAN_PATH);

  const knowledgeRow = page.locator('.study-plan__row').filter({ hasText: KNOWLEDGE_TASK });
  await knowledgeRow.getByRole('link').click();
  await expect(page).toHaveURL(new RegExp(`/exam/cs408/knowledge.*module=${MODULE}`));

  await page.goto(PLAN_PATH);
  const practiceRow = page.locator('.study-plan__row').filter({ hasText: PRACTICE_TASK });
  await practiceRow.getByRole('link').click();
  await expect(page).toHaveURL(new RegExp(`/exam/cs408/practice.*module=${MODULE}`));

  await page.goto(PLAN_PATH);
  await page.screenshot({ path: path.join(SCREENSHOTS, 'real-desktop-plan-action.png'), fullPage: true });

  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  expect(errors).toEqual([]);
});

// ================================================================ §12 factual completion

test('the derived status follows a real factual action, with no frontend write', async ({ page, request }) => {
  await apiLogin(request, PAID);

  // Start from a known incomplete state. The learner state is real and persistent, so this
  // resets it with the same factual action a learner would use — it is not a stub.
  const probe = await readPlan(request);
  const leaves = sectionLeaves(probe, probe.tasks.find((t) => t.title === KNOWLEDGE_TASK)?.knowledge_point_name ?? '');
  expect(leaves.length, 'the section must expose the leaves the backend counts').toBeGreaterThan(0);
  await setKnowledge(request, leaves, 'not_started');

  const before = await readPlan(request);
  const task = before.tasks.find((t) => t.title === KNOWLEDGE_TASK);
  expect(task, 'the seeded task must exist').toBeTruthy();
  expect(task?.computed_status, 'starts incomplete').toBe('not_started');

  await loginAs(page, PAID);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(PLAN_PATH);
  const traffic = frontendTraffic(page);
  const row = page.locator('.study-plan__row').filter({ hasText: KNOWLEDGE_TASK });
  await expect(row.locator('.study-plan__status')).toHaveText('未开始');

  // the REAL factual action, issued outside the page
  await setKnowledge(request, leaves, 'mastered');

  // the page refreshes the canonical plan and picks up the change
  await page.reload();
  const refreshed = page.locator('.study-plan__row').filter({ hasText: KNOWLEDGE_TASK });
  await expect(refreshed.locator('.study-plan__status')).toHaveText('已完成', { timeout: 15_000 });
  expect((await readPlan(request)).tasks.find((t) => t.title === KNOWLEDGE_TASK)?.computed_status).toBe('completed');

  // the frontend never wrote a status: no task mutation, no checkbox, no completion control
  expect(traffic.filter((r) => /\/study-plan\/tasks/.test(r.url))).toEqual([]);
  expect(traffic.filter((r) => r.method !== 'GET' && r.url.includes('/study-plan'))).toEqual([]);
  await expect(page.locator('input[type="checkbox"]')).toHaveCount(0);
});

// ================================================================ §9 optional mapping

test('a missing learning_plan entry is treated as denied, never as a crash', async ({ page, request }) => {
  // TWO pieces of evidence, and only the second substitutes a response:
  //
  // (1) LIVE — the real endpoint returns `features: {}` for a direction with no feature
  //     quota, so the empty map is a genuine runtime shape and not a hypothetical.
  // (2) The component renders that shape safely. `exam_11408` can never return `{}` without
  //     changing product policy (forbidden here), so this single check substitutes the
  //     entitlement response. It is the ONLY response substituted anywhere in this spec —
  //     the free gate proof and the paid ledger proof above are both un-intercepted.
  await apiLogin(request, PAID);
  const empty = await request.get(`${API}/membership/entitlements?service_key=programming`);
  expect(empty.status()).toBe(200);
  expect((await empty.json()).features).toEqual({});

  const errors = consoleProblems(page);
  await page.route('**/membership/entitlements*', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json',
      body: JSON.stringify({ service_key: 'exam_11408', current_plan: 'free', features: {} }) });
  });
  await loginAs(page, PAID);
  await page.goto(PLAN_PATH);
  await expect(page.getByText('当前会员暂未开放学习计划')).toBeVisible();
  expect(errors).toEqual([]);
});

// ================================================================ §16 two users

test('a second learner never sees another learner plan', async ({ page, request }) => {
  await apiLogin(request, OTHER);
  const own = await readPlan(request);
  expect(own.tasks.map((t) => t.title)).toEqual([OTHER_TASK]);

  await loginAs(page, OTHER);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(PLAN_PATH);
  await expect(page.locator('.study-plan__row').filter({ hasText: OTHER_TASK })).toHaveCount(1);
  await expect(page.locator('.study-plan__row').filter({ hasText: KNOWLEDGE_TASK })).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(KNOWLEDGE_TASK);
});
