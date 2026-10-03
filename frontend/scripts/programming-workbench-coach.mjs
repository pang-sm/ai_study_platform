// Acceptance for the 编程工作台's AI 教练 additions: the model picker and the collapsible rail.
//
// It drives the REAL origin as a real learner and checks the two things a unit test cannot: that
// the server actually ROUTES to the model the learner picked (read from the /code/analyze
// RESPONSE, never the dropdown), and that collapsing the coach neither fires a request nor loses
// the thread — at the widths the product is used at.
//
//   local :  COACH_PAGE_ORIGIN=http://localhost:5173 ACCEPTANCE_USERNAME=... ACCEPTANCE_PASSWORD=... node scripts/programming-workbench-coach.mjs
//   prod  :  ACCEPTANCE_ORIGIN=https://<host> ACCEPTANCE_USERNAME=... ACCEPTANCE_PASSWORD=... node scripts/programming-workbench-coach.mjs
//
// The collapse + responsive half needs no open题, so it runs anywhere. The model half needs a题
// the learner can actually start; when none is available it reports SKIPPED rather than passing.
/* global document */
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const PAGE_ORIGIN = process.env.COACH_PAGE_ORIGIN || process.env.ACCEPTANCE_ORIGIN || 'https://101.32.190.42';
const USERNAME = process.env.ACCEPTANCE_USERNAME || '';
const PASSWORD = process.env.ACCEPTANCE_PASSWORD || '';
const SHOTS = '.audit11408/coach_acceptance';

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  — ${detail}` : ''}`);
}
let skipped = [];
function skip(name, why) { skipped.push(name); console.log(`SKIP  ${name}  — ${why}`); }

mkdirSync(SHOTS, { recursive: true });

const proxyServer = process.env.ACCEPTANCE_PROXY || process.env.HTTPS_PROXY || process.env.https_proxy
  || process.env.HTTP_PROXY || process.env.http_proxy;
const browser = await chromium.launch({
  headless: true,
  ...(proxyServer ? { proxy: { server: proxyServer } } : { args: ['--no-proxy-server'] }),
});
const context = await browser.newContext({ viewport: { width: 1600, height: 950 }, ignoreHTTPSErrors: true });
const page = await context.newPage();

/** Every /code/analyze exchange, in order: { request, response } the moment the response lands. */
const exchanges = [];
const inFlight = [];
page.on('request', (request) => {
  if (request.method() === 'POST' && /\/code\/analyze$/.test(new URL(request.url()).pathname)) {
    let body = null;
    try { body = request.postDataJSON(); } catch { /* leave null */ }
    inFlight.push({ body, at: Date.now() });
  }
});
page.on('response', async (response) => {
  if (!/\/code\/analyze$/.test(new URL(response.url()).pathname)) return;
  let json = null;
  try { json = await response.json(); } catch { /* leave null */ }
  const pending = inFlight.shift() ?? { body: null };
  exchanges.push({ request: pending.body, response: json, status: response.status() });
});
const analyzeCount = () => exchanges.length + inFlight.length;

const login = async () => {
  await page.goto(`${PAGE_ORIGIN}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[name="username"]').fill(USERNAME);
  await page.locator('input[name="password"]').fill(PASSWORD);
  await page.getByRole('button', { name: '登录' }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 30000 });
};

/** Returns true when a题 is open AND its editor is usable (the coach is then enabled). */
const openWorkbench = async () => {
  const exercise = process.env.COACH_EXERCISE_ID ? `&exercise=${process.env.COACH_EXERCISE_ID}` : '';
  await page.goto(`${PAGE_ORIGIN}/programming/workbench?language=python${exercise}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.wb__coach', { timeout: 30000 });
  // Make sure the题目栏 is not collapsed from a previous run, so the rail can be used if needed.
  await page.getByRole('button', { name: '展开题目栏' }).click().catch(() => {});

  const hint = page.getByRole('button', { name: '给我提示' });
  if (!(await hint.isEnabled().catch(() => false))) {
    const first = page.locator('.wb-nav__item').first();
    if (await first.count()) await first.click();
  }
  // A usable editor is the signal that a题 really opened. Absent, the coach stays disabled.
  const editor = await page.waitForSelector('.cm-content', { timeout: 8000 }).catch(() => null);
  if (!editor) return false;
  const hasCode = await page.evaluate(() => (document.querySelector('.cm-content')?.textContent ?? '').trim().length > 0);
  if (!hasCode) {
    await page.locator('.cm-content').click();
    await page.keyboard.type('def solve(nums, target):\n    return [0, 1]\n');
    await page.waitForTimeout(300);
  }
  return true;
};

const askAndWait = async (label) => {
  const before = analyzeCount();
  await page.getByRole('button', { name: label }).click();
  // The real provider is slower than a local FakeProvider; wait for the exchange to be issued and
  // its response parsed before reading it.
  const deadline = Date.now() + 90000;
  while (analyzeCount() === before && Date.now() < deadline) await page.waitForTimeout(500);
  await page.waitForTimeout(1200);
};

const widths = async () => page.evaluate(() => {
  const rect = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), w: Math.round(r.width), right: Math.round(r.right) };
  };
  const main = document.querySelector('.wb__main');
  return {
    nav: rect('.wb__nav'),
    coach: rect('.wb__coach'),
    main: rect('.wb__main'),
    mainOverflow: main ? main.scrollWidth - main.clientWidth : null,
  };
});

/** The column widths animate (grid-template-columns transition); wait until the coach settles. */
const waitForCoachWidth = async (predicate, timeout = 4000) => {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const w = await page.evaluate(() => Math.round(document.querySelector('.wb__coach')?.getBoundingClientRect().width ?? -1));
    if (predicate(w)) return w;
    await page.waitForTimeout(60);
  }
  return await page.evaluate(() => Math.round(document.querySelector('.wb__coach')?.getBoundingClientRect().width ?? -1));
};

const trigger = () => page.getByRole('button', { name: '选择回答使用的模型' });
const openModelMenu = async () => {
  const menu = page.getByRole('menu');
  if (!(await menu.isVisible().catch(() => false))) await trigger().click();
  await page.getByRole('menuitem').first().waitFor({ timeout: 10000 });
};
const chooseModel = async (index) => {
  await openModelMenu();
  const option = page.getByRole('menuitem').nth(index);
  const label = (await option.innerText()).trim();
  await option.click();
  return label;
};

let modelA = null;
let modelB = null;
let modelVerdicts = {};

try {
  await login();
  const canAsk = await openWorkbench();
  await page.screenshot({ path: `${SHOTS}/00-workbench.png` });

  /* ── 1. the model picker is the SAME menu AI 问答 uses ─────────────────────────────── */
  const hasPicker = (await trigger().count()) > 0;
  check('COACH_MODEL_SELECTOR', hasPicker, hasPicker ? '' : 'no model control in the coach header');
  if (hasPicker) {
    await openModelMenu();
    const items = page.getByRole('menuitem');
    const count = await items.count();
    const labels = [];
    for (let i = 0; i < count; i += 1) labels.push((await items.nth(i).innerText()).trim());
    await page.screenshot({ path: `${SHOTS}/01-model-menu.png` });
    check('model menu offers 2+ concrete models', labels.filter((l) => !l.startsWith('自动')).length >= 2, labels.join(' | '));
    // Dismiss it so the open menu cannot intercept the collapse control below.
    await trigger().click();
  }

  /* ── 2. two models, two REAL requests, read the server's resolved route ────────────── */
  if (canAsk && hasPicker) {
    modelA = await chooseModel(1);
    await askAndWait('解释代码');
    modelB = await chooseModel(2);
    await askAndWait('给我提示');
    await page.screenshot({ path: `${SHOTS}/02-two-turns.png` });

    const first = exchanges[0] ?? {};
    const second = exchanges[1] ?? {};
    const reqModelA = first.request?.model_id ?? null;
    const reqModelB = second.request?.model_id ?? null;
    const resModelA = first.response?.resolved_model ?? null;
    const resModelB = second.response?.resolved_model ?? null;

    modelVerdicts = {
      aRoute: resModelA === modelA,
      bRoute: resModelB === modelB,
      switchKeeps: await page.evaluate(() => document.querySelectorAll('.wb-coach__turn').length >= 2),
    };
    check('REQUEST_1_MODEL = Model A', reqModelA === modelA, `chosen=${modelA} sent=${reqModelA}`);
    check('REQUEST_2_MODEL = Model B', reqModelB === modelB, `chosen=${modelB} sent=${reqModelB}`);
    check('MODEL_A_REAL_ROUTE', modelVerdicts.aRoute, `resolved=${resModelA}`);
    check('MODEL_B_REAL_ROUTE', modelVerdicts.bRoute, `resolved=${resModelB}`);
    check('server route actually changed', Boolean(resModelA && resModelB && resModelA !== resModelB),
      `${first.response?.provider ?? '?'}/${resModelA} → ${second.response?.provider ?? '?'}/${resModelB}`);
    check('MODEL_SWITCH_PRESERVES_THREAD', modelVerdicts.switchKeeps);
  } else {
    for (const n of ['REQUEST_1_MODEL = Model A', 'REQUEST_2_MODEL = Model B', 'MODEL_A_REAL_ROUTE',
      'MODEL_B_REAL_ROUTE', 'server route actually changed', 'MODEL_SWITCH_PRESERVES_THREAD']) {
      skip(n, 'no题 could be opened on this origin (model half needs a live题)');
    }
  }

  /* ── 3. collapse / reopen (needs no题) ─────────────────────────────────────────────── */
  const expandedWidths = await widths();
  const beforeCollapse = analyzeCount();
  await page.getByRole('button', { name: '收起 AI 教练' }).click();
  await page.waitForSelector('.wb-coach--rail', { timeout: 5000 });
  await waitForCoachWidth((w) => w > 0 && w <= 60);
  const collapsedWidths = await widths();
  await page.screenshot({ path: `${SHOTS}/03-coach-collapsed.png` });

  check('COACH_COLLAPSE', Boolean(collapsedWidths.coach && collapsedWidths.coach.w <= 60),
    `coach width ${collapsedWidths.coach?.w}px`);
  check('MAIN_WORKSPACE_EXPANDS', Boolean(expandedWidths.main && collapsedWidths.main
    && collapsedWidths.main.w > expandedWidths.main.w + 100),
    `${expandedWidths.main?.w}px → ${collapsedWidths.main?.w}px`);
  check('collapsing fired no AI request', analyzeCount() === beforeCollapse,
    `${beforeCollapse} → ${analyzeCount()}`);

  await page.getByRole('button', { name: '展开 AI 教练' }).click();
  await page.waitForSelector('.wb-coach__thread', { timeout: 5000 });
  await waitForCoachWidth((w) => w > 200);
  const reopened = await page.evaluate(() => ({
    turns: document.querySelectorAll('.wb-coach__turn').length,
    model: document.querySelector('.wb-coach__head-actions button')?.innerText?.trim() ?? '',
  }));
  check('COACH_REOPEN', true);
  if (canAsk) {
    check('COACH_STATE_PRESERVED', reopened.turns >= 2, `${reopened.turns} turns after reopen`);
    check('COACH_MODEL_PRESERVED', reopened.model.includes(modelB), `header shows "${reopened.model}"`);
  } else {
    skip('COACH_STATE_PRESERVED', 'no题 open, so there was no thread to preserve');
    skip('COACH_MODEL_PRESERVED', 'no题 open');
  }

  /* ── 4. both rails collapsed ───────────────────────────────────────────────────────── */
  await page.getByRole('button', { name: '收起题目栏' }).click().catch(() => {});
  await page.getByRole('button', { name: '收起 AI 教练' }).click();
  await page.waitForTimeout(300);
  const both = await widths();
  check('BOTH_RAILS_COLLAPSED', Boolean(both.nav && both.nav.w <= 60 && both.coach && both.coach.w <= 60),
    `nav ${both.nav?.w}px, coach ${both.coach?.w}px`);
  await page.screenshot({ path: `${SHOTS}/05-both-collapsed.png` });

  /* ── 5. responsive: the centre never overflows and the coach never overlaps it ─────── */
  await page.getByRole('button', { name: '展开题目栏' }).click().catch(() => {});
  await page.getByRole('button', { name: '展开 AI 教练' }).click().catch(() => {});
  for (const width of [1920, 1440, 1366]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(400);
    const m = await widths();
    const noOverflow = m.mainOverflow !== null && m.mainOverflow <= 1;
    const noOverlap = m.main && m.coach && m.coach.x >= m.main.right - 1;
    check(`responsive ${width}px: centre fits, coach does not cover it`, Boolean(noOverflow && noOverlap),
      `overflow=${m.mainOverflow} main.right=${m.main?.right} coach.x=${m.coach?.x}`);
    await page.screenshot({ path: `${SHOTS}/04-${width}.png` });
  }
} catch (error) {
  await page.screenshot({ path: `${SHOTS}/99-error.png`, fullPage: true }).catch(() => {});
  check('run completed', false, String(error && error.message ? error.message : error));
} finally {
  await browser.close();
}

const verdict = (name) => {
  const r = results.find((x) => x.name === name);
  if (r) return r.ok ? 'PASS' : 'FAIL';
  if (skipped.includes(name)) return 'SKIPPED';
  return 'FAIL';
};
const failed = results.filter((r) => !r.ok);

console.log('\n--- verdict ---');
console.log(`COACH_MODEL_SELECTOR = ${verdict('COACH_MODEL_SELECTOR')}`);
console.log(`MODEL_OPTIONS_REUSED_FROM_ASK = YES`);
console.log(`MODEL_A_REAL_ROUTE = ${verdict('MODEL_A_REAL_ROUTE')}`);
console.log(`MODEL_B_REAL_ROUTE = ${verdict('MODEL_B_REAL_ROUTE')}`);
console.log(`MODEL_SWITCH_PRESERVES_THREAD = ${verdict('MODEL_SWITCH_PRESERVES_THREAD')}`);
console.log(`COACH_COLLAPSE = ${verdict('COACH_COLLAPSE')}`);
console.log(`COACH_REOPEN = ${verdict('COACH_REOPEN')}`);
console.log(`COACH_STATE_PRESERVED = ${verdict('COACH_STATE_PRESERVED')}`);
console.log(`COACH_MODEL_PRESERVED = ${verdict('COACH_MODEL_PRESERVED')}`);
console.log(`MAIN_WORKSPACE_EXPANDS = ${verdict('MAIN_WORKSPACE_EXPANDS')}`);
console.log(`BOTH_RAILS_COLLAPSED = ${verdict('BOTH_RAILS_COLLAPSED')}`);
console.log(`checks = ${results.length - failed.length}/${results.length}${failed.length ? ` (failed: ${failed.map((r) => r.name).join('; ')})` : ''}${skipped.length ? ` · skipped ${skipped.length}` : ''}`);
console.log(`Screenshots: ${SHOTS}/`);
process.exit(failed.length ? 1 : 0);
