// Public acceptance for the 编程工作台 (the IDE-shaped programming workspace).
//
// Drives the REAL production origin in Chromium as the acceptance learner and checks the new
// information architecture end to end: the front door asks for a language, choosing one opens that
// language's workspace, the workspace is the three-column IDE, switching题目 happens inside it, and
// 运行 goes through the real judge (buffer written to the project, project executed).
//
// It ends with TWO INDEPENDENT verdicts, never one number: IDE_UI_ACCEPTANCE (the workspace and its
// wiring) and SECURE_CODE_EXECUTION (the environment's own state — UNAVAILABLE under SECURITY_S0 by
// design, AVAILABLE when a sandbox is live). See the verdict block at the foot of the file.
//
//   ACCEPTANCE_USERNAME=... ACCEPTANCE_PASSWORD=... node scripts/acceptance/programming_workbench_ide_acceptance.mjs
//
// Without credentials it still runs the anonymous half: that the deployed bundle boots and the
// space's route resolves (a signed-out visitor is sent to /login rather than to a blank page).
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const ORIGIN = process.env.ACCEPTANCE_ORIGIN || 'https://101.32.190.42';
const USERNAME = process.env.ACCEPTANCE_USERNAME || '';
const PASSWORD = process.env.ACCEPTANCE_PASSWORD || '';
const SHOTS = '.audit11408/ide_workbench';
const LANGUAGE = process.env.ACCEPTANCE_LANGUAGE || 'python';

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  — ${detail}` : ''}`);
}

mkdirSync(SHOTS, { recursive: true });

// Chromium does not inherit the shell's proxy environment, so reaching the public origin from a
// machine behind one needs it handed over explicitly.
//
// The two branches are mutually exclusive on purpose: `--no-proxy-server` does not merely skip a
// proxy, it DISABLES proxying for the whole browser, so passing it alongside `proxy` would make
// the proxy inert. It is kept as the no-proxy default because that is the behaviour this harness
// has always had, and it is what keeps a loopback-targeted run from being intercepted.
//
// Only whether a proxy is in use is printed — never the URL itself, which may carry credentials.
const proxyServer =
  process.env.ACCEPTANCE_PROXY ||
  process.env.HTTPS_PROXY ||
  process.env.https_proxy ||
  process.env.HTTP_PROXY ||
  process.env.http_proxy;

console.log(`PROXY = ${proxyServer ? 'enabled' : 'disabled'}`);
const browser = await chromium.launch({
  headless: true,
  ...(proxyServer ? { proxy: { server: proxyServer } } : { args: ['--no-proxy-server'] }),
});
const context = await browser.newContext({ viewport: { width: 1600, height: 950 }, ignoreHTTPSErrors: true });
const page = await context.newPage();

const consoleErrors = [];
const failedRequests = [];
page.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text().slice(0, 240)); });
// Every API response the page receives, as PATH + STATUS. This is what names a non-2xx instead of
// leaving "a 401 happened somewhere" to be guessed at.
const apiStatuses = [];
page.on('response', (response) => {
  let pathname = '';
  try { pathname = new URL(response.url()).pathname; } catch { return; }
  if (!pathname.startsWith('/api/')) return;
  apiStatuses.push({ status: response.status(), method: response.request().method(), pathname });
});

// Method + PATHNAME only (never the query string), so nothing a request carries by way of
// credentials or identity can reach the log. Document navigations are excluded on purpose: a
// document load that FAILED on attempt 1 and then SUCCEEDED on attempt 2 is the retry doing its
// job, not a page whose resources are broken — and counting it here would make every run of a
// flaky link look like a failed deploy.
page.on('requestfailed', (request) => {
  if (request.resourceType() === 'document') return;
  let pathname = request.url();
  try { pathname = new URL(request.url()).pathname; } catch { /* keep as-is */ }
  failedRequests.push(`${request.method()} ${pathname} (${request.failure()?.errorText ?? 'failed'})`);
});

// Auth calls, recorded as METHOD + PATHNAME + STATUS only. Pathname carries no query string, and no
// header or body is ever read, so a cookie, bearer token or password cannot reach this log.
const authResponses = [];
page.on('response', (response) => {
  let pathname = '';
  try { pathname = new URL(response.url()).pathname; } catch { return; }
  if (/\/(login|logout|me|session|auth)/.test(pathname)) {
    authResponses.push(`${response.request().method()} ${pathname} -> ${response.status()}`);
  }
});

/**
 * What the browser is ACTUALLY showing when a wait gives up.
 *
 * A blank body would otherwise be read as "the app did not render" — which is a claim about the
 * product, and it should not be inferred from a timeout. This prints the page itself: where it is,
 * what it is titled, and the first 300 characters of its text — plus the two things this script has
 * already collected that explain a page which rendered nothing (a console error, or a request the
 * page needed that failed). Auth calls are reported as method + pathname + status only.
 */
async function diagnose(message) {
  console.log(`\n${message}`);
  let state = null;
  try {
    state = await page.evaluate(() => ({
      url: window.location.href,
      title: document.title,
      body: (document.body?.innerText ?? '').slice(0, 300),
    }));
  } catch (error) {
    console.log(`  (page state unavailable: ${String(error.message).split('\n')[0]})`);
  }
  if (state) {
    console.log(`CURRENT_URL = ${state.url}`);
    console.log(`PAGE_TITLE = ${state.title}`);
    console.log(`BODY_TEXT = ${JSON.stringify(state.body)}`);
  }
  console.log(`AUTH_RESPONSES = ${authResponses.length ? authResponses.join(' | ') : '(none seen)'}`);
  // Already collected by this script: a blank page has exactly two ordinary causes — the bundle
  // threw, or a request it needed failed — so both are printed here rather than left to be guessed.
  console.log(`PAGE_ERRORS = ${consoleErrors.length ? consoleErrors.slice(0, 3).join(' | ') : '(none)'}`);
  console.log(`FAILED_REQUESTS = ${failedRequests.length ? failedRequests.slice(0, 3).join(' | ') : '(none)'}`);
  await page.screenshot({ path: `${SHOTS}/99-timeout-state.png` }).catch(() => {});
}

/**
 * A navigation, with a bounded retry.
 *
 * Two things are deliberate here, and both come from measurements of this origin rather than taste:
 *
 * 1. `domcontentloaded`, NOT `networkidle`. Idle waits for every connection the page opens — and
 *    the SPA fires its boot API calls from the same document — so a reset on ANY of those in-flight
 *    requests rejects the whole navigation. The DOM being parsed is the only precondition the
 *    checks below need, and each of them waits for its own landmark anyway.
 * 2. A retry. The path to this origin crosses a proxy and a long-haul link, and single resets do
 *    happen: the exact same proxy+context configuration that now measures 24/24 successes produced
 *    `net::ERR_CONNECTION_CLOSED` on earlier attempts. One attempt is not a verdict about a deploy.
 */
async function gotoWithRetry(url, { attempts = 3 } = {}) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45_000 });
    } catch (error) {
      lastError = error;
      console.log(`  (navigation attempt ${attempt}/${attempts} failed: ${String(error.message).split('\n')[0]})`);
      await page.waitForTimeout(1_000 * attempt);
    }
  }
  throw lastError;
}

/** Waits for a condition, and answers whether it was reached rather than aborting the run. */
async function settledWithin(predicate, timeout) {
  try {
    await page.waitForFunction(predicate, null, { timeout });
    return true;
  } catch {
    return false;
  }
}

/* ── the sign-in screen's own landmarks ──────────────────────────────────────────
   Read off the real screen (`features/auth/components/login-page.tsx`), not invented. There is no
   `data-testid` convention anywhere in this app, so the most stable hooks the page actually has are
   the ones it already exposes:
     · `#login-panel-password` — the id `PANEL_IDS.password` wires the 密码登录 tab to its panel
       through `aria-controls`, so it is structural rather than cosmetic; and only the password
       panel is rendered while that tab is selected, which is the default.
     · `input[name="username"]` / `input[name="password"]` — the FORM CONTRACT react-hook-form
       registers (`{...register('username')}`), which is what the field submits under.
   None of the three depends on copy, on a class name, or on how much text happens to be on the
   page — which is what the previous `body.innerText.length > 50` gate got wrong: length says
   nothing about WHICH screen rendered, or whether it rendered at all. */
const loginPanel = page.locator('#login-panel-password');
const usernameInput = loginPanel.locator('input[name="username"]');
const passwordInput = loginPanel.locator('input[name="password"]');

/* ── anonymous half: a signed-out visitor is sent to the real sign-in screen ─────── */
await gotoWithRetry(`${ORIGIN}/programming`);
try {
  // The redirect is client-side, so the address proves nothing until the router has run; then the
  // screen's own controls must be on screen. Three conditions, in the order they become true.
  await page.waitForURL((url) => url.pathname === '/login', { timeout: 30_000 });
  await loginPanel.waitFor({ state: 'visible', timeout: 30_000 });
  await usernameInput.waitFor({ state: 'visible', timeout: 30_000 });
  await passwordInput.waitFor({ state: 'visible', timeout: 30_000 });
} catch (error) {
  await diagnose('the sign-in screen was not reached or did not render (URL + landmark waits) —');
  throw error;
}
const anonymousPath = new URL(page.url()).pathname;
const usernameFields = await usernameInput.count();
const passwordFields = await passwordInput.count();
check(
  'a signed-out visitor is sent to the real sign-in screen, with its form rendered',
  anonymousPath === '/login' && usernameFields === 1 && passwordFields === 1,
  `pathname=${anonymousPath}, username fields=${usernameFields}, password fields=${passwordFields}`,
);

if (!USERNAME || !PASSWORD) {
  console.log('\nACCEPTANCE_USERNAME / ACCEPTANCE_PASSWORD are not set — the authenticated half was skipped.');
  await browser.close();
  process.exit(2);
}

/* ── sign in ─────────────────────────────────────────────────────────────────────── */
await page.locator('input[type="password"]').first().waitFor({ timeout: 30_000 });
const userBox = page.locator('input[type="text"], input:not([type])').first();
await userBox.fill(USERNAME);
await page.locator('input[type="password"]').first().fill(PASSWORD);
await page.getByRole('button', { name: /登\s*录/ }).first().click();
await page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 45_000 });
check('signs in', true, new URL(page.url()).pathname);

/* ── the front door ─────────────────────────────────────────────────────────────── */
await gotoWithRetry(`${ORIGIN}/programming`);
// Settle on the front door's own landmark rather than on a fixed delay: this page either resolves
// the language itself (and swaps to the workspace) or asks. Waiting for either one to exist is what
// makes the branch below a reading of the app instead of a race against it.
await page
  .waitForFunction(
    () => Boolean(document.querySelector('.wb__bar')) || /选择编程语言/.test(document.body.innerText),
    null,
    { timeout: 30_000 },
  )
  .catch(() => {});
let path = new URL(page.url()).pathname;
if (path === '/programming' || path === '/programming/') {
  // No language recalled: the front door must be the four-language question and nothing else.
  const heading = await page.getByRole('heading', { level: 1 }).first().innerText().catch(() => '');
  check('the front door asks which language', heading.includes('选择编程语言'), heading);
  await page.screenshot({ path: `${SHOTS}/01-front-door.png`, fullPage: true });
  await page.getByRole('button', { name: /Python/ }).first().click();
  await page.waitForURL((url) => url.pathname.startsWith('/programming/workbench'), { timeout: 30_000 });
  path = new URL(page.url()).pathname;
} else {
  check('a recalled language goes straight back to the workspace', path.startsWith('/programming/workbench'), path);
  await page.screenshot({ path: `${SHOTS}/01-resumed-workspace.png`, fullPage: true });
}

/* ── the workspace: three columns ───────────────────────────────────────────────── */
check('the workspace route is open', path.startsWith('/programming/workbench'), path);
check('the language is read as context', await page.locator('#wb-language').count() === 1);

const rail = page.getByRole('navigation', { name: '题目导航' });
await rail.waitFor({ timeout: 30_000 });
check('the rail carries a题目 search', await page.getByRole('searchbox', { name: '搜索题目' }).count() === 1);
// Wait for a BANK item specifically, not just any group. The rail paints the recommendation group
// first (it comes from its own read), so "a group exists" is true before the bank lands — measuring
// the grouping then counts the recommendations and nothing else. A status mark is rendered on bank
// items ONLY, so waiting for one is waiting for the bank.
await rail.locator('.wb-nav__mark').first().waitFor({ state: 'visible', timeout: 30_000 });
const chapterCount = await rail.locator('.wb-nav__group:has(.wb-nav__mark)').count();
const bankItems = await rail.locator('.wb-nav__item:has(.wb-nav__mark)').count();
check('the rail is the language bank, grouped by chapter', chapterCount >= 2 && bankItems > 1,
  `${chapterCount} chapters, ${bankItems} exercises`);

// The editor is the real CodeMirror, not a textarea: `.cm-editor` is its own root element.
await page.locator('.cm-editor').first().waitFor({ timeout: 30_000 });
check('the centre is a real code editor (CodeMirror, not a textarea)', await page.locator('.cm-editor').count() === 1);
check('the editor has a line-number gutter', await page.locator('.cm-gutters').count() === 1);

for (const label of ['测试结果', '控制台', '提交记录']) {
  check(`the bottom panel has ${label}`, await page.getByRole('tab', { name: new RegExp(label) }).count() === 1);
}
check('the AI coach has its own rail', await page.getByRole('complementary', { name: 'AI 教练' }).count() === 1);
await page.screenshot({ path: `${SHOTS}/02-workspace.png`, fullPage: true });

/* ── switching题目 happens INSIDE the page ─────────────────────────────────────── */
const crumbBefore = await page.locator('.wb__crumb-title').first().innerText();
const items = rail.locator('.wb-nav__item');
const itemCount = await items.count();
if (itemCount > 1) {
  await items.nth(1).click();
  await page.waitForFunction(
    (before) => document.querySelector('.wb__crumb-title')?.textContent !== before,
    crumbBefore,
    { timeout: 30_000 },
  );
  const crumbAfter = await page.locator('.wb__crumb-title').first().innerText();
  const urlAfter = new URL(page.url());
  check(
    'choosing another题 swaps the centre without leaving the workspace',
    urlAfter.pathname.startsWith('/programming/workbench') && urlAfter.searchParams.get('exercise') !== null,
    `${crumbBefore} -> ${crumbAfter}`,
  );
} else {
  check('choosing another题 swaps the centre without leaving the workspace', false, 'the bank served only one题');
}
await page.screenshot({ path: `${SHOTS}/03-switched-exercise.png`, fullPage: true });

/* ── the real judge: 运行 writes the buffer to the project, then runs it ─────────── */
await page.getByRole('button', { name: '运行', exact: true }).first().click();
await page.getByRole('tab', { name: '控制台' }).click();
// SETTLED, not started: the panel says 正在运行 the moment the request goes out, and accepting that
// as a verdict is how a check passes while the judge is still working (or has just failed). The
// wait is bounded and non-fatal on purpose — a step that never settles must not abort the run
// before the API dump prints, because that dump is what says WHY.
const runSettled = await settledWithin(
  () => {
    const panel = document.querySelector('[role=tabpanel]')?.textContent || '';
    const page = document.body.innerText;
    const settledPanel = /退出码|stdout|stderr|没有产生输出/.test(panel) && !/正在运行/.test(panel);
    // The workbench's own sentences for a failed judge call — the generic one, and the specific one
    // shown when the run environment is off (SECURITY_S0). Matched EXACTLY rather than by loose
    // tokens, so a word inside a real answer can never be mistaken for a failure.
    return settledPanel || /这次操作没有成功|代码运行环境当前不可用/.test(page);
  },
  120_000,
);
const consoleText = await page.locator('[role=tabpanel]').innerText();
const runStatus = [...apiStatuses].reverse().find((entry) => /\/run$/.test(entry.pathname))?.status;
const verdictRendered = /退出码|stdout|stderr|没有产生输出/.test(consoleText) && !/正在运行/.test(consoleText);
// SECURITY_S0 is fail-closed: production runs no learner code until a sandbox passes independent
// acceptance, so the INTENDED answer to 运行 is 503 `code_execution_unavailable`. That is a clean
// refusal, and it is a different outcome from a 500 — which is what this route used to return.
const refusedCleanly = runStatus === 503;
// The environment's state, read separately from the UI checks. UNAVAILABLE is the expected
// production state under SECURITY_S0 and is NOT a failure of this run — it is a different, narrower
// question than "does the IDE wire 运行 to the real judge", which is what the check below asks.
const codeExecutionState = refusedCleanly ? 'UNAVAILABLE' : verdictRendered ? 'AVAILABLE' : 'UNKNOWN';
check(
  '运行 reaches the real judge and the call is answered',
  verdictRendered || refusedCleanly,
  `run HTTP=${runStatus ?? '(no response)'}; code execution=${codeExecutionState}; `
    + consoleText.split('\n').filter(Boolean).slice(0, 2).join(' / ').slice(0, 140),
);
await page.screenshot({ path: `${SHOTS}/04-run-result.png`, fullPage: true });

/* ── the coach answers with the work in front of it ─────────────────────────────── */
await page.getByRole('button', { name: '解释代码' }).click();
// Same rule as the run: 正在分析 is a request in flight, not an answer. Wait for the turn to settle
// — a real answer, or the panel's own failure sentence — so a rejected call cannot pass as success.
const coachSettled = await settledWithin(
  () => {
    const thread = document.querySelector('.wb-coach__thread');
    if (!thread) return false;
    // Pending is read from the ELEMENT the panel renders for it, never from the thread's text: the
    // answer is prose, and prose is free to contain the words the indicator happens to use.
    if (thread.querySelector('.wb-coach__pending')) return false;
    // ONE turn is one question AND its answer — the panel renders the pair as a single `.wb-coach__turn`
    // — so the thing that proves an answer arrived is an `.wb-coach__answer`, not a turn count.
    return thread.querySelectorAll('.wb-coach__answer').length >= 1;
  },
  120_000,
);
const coachText = await page.locator('.wb-coach__thread').innerText();
const coachStatus = [...apiStatuses].reverse().find((entry) => /\/code\/analyze$/.test(entry.pathname))?.status;
const coachFailed = /这次分析没有成功/.test(coachText);
check(
  'the coach answers about this题目 and this code',
  coachSettled && !coachFailed && coachStatus === 200,
  `analyze HTTP=${coachStatus ?? '(no response)'}; settled=${coachSettled}; `
    + coachText.replace(/\s+/g, ' ').slice(-150),
);
await page.screenshot({ path: `${SHOTS}/05-coach.png`, fullPage: true });

/* ── console hygiene ───────────────────────────────────────────────────────────── */
// Which API calls answered, by path and status — printed in full so a non-2xx is NAMED here rather
// than inferred from the console. A 401 on a specific path is a different problem from a 404 on a
// different one, and the console only ever says "a resource failed".
console.log('\n--- API responses (path + status, in order) ---');
console.log(apiStatuses.length
  ? apiStatuses.map((entry) => `${entry.status} ${entry.method} ${entry.pathname}`).join('\n')
  : '(none)');

// Two console errors are the app working as intended, and both are counted here as such:
//   · a 401 on the session probe — "am I signed in?" being answered no for a signed-out visitor;
//   · a 503 from the code-execution gate — SECURITY_S0 refuses learner code by design until a
//     sandbox passes acceptance, so the browser logging that refusal is the policy, not a fault.
const sawPreLoginProbe = apiStatuses.some((entry) => entry.pathname === '/api/me' && entry.status === 401);
const sawPolicyRefusal = apiStatuses.some((entry) => entry.status === 503 && /\/(run|test|submit)$/.test(entry.pathname));
const expectedConsoleNoise = [
  sawPreLoginProbe ? /401/ : null,
  sawPolicyRefusal ? /503/ : null,
].filter(Boolean);
const unexpectedErrors = consoleErrors.filter((text) => !expectedConsoleNoise.some((pattern) => pattern.test(text)));
// ERR_ABORTED is a request the app itself cancelled (React Query superseding an in-flight read),
// not a request that failed to arrive.
const realFailures = failedRequests.filter((entry) => !/ERR_ABORTED/.test(entry));
check('no unexpected page errors', unexpectedErrors.length === 0,
  `pre-login 401 probe=${sawPreLoginProbe}, policy refusal=${sawPolicyRefusal}; ` +
    unexpectedErrors.slice(0, 2).join(' | '));
check('no failed requests', realFailures.length === 0, realFailures.slice(0, 2).join(' | '));

await browser.close();

const failed = results.filter((entry) => !entry.ok);

/*
 * TWO INDEPENDENT VERDICTS, PRINTED SEPARATELY — this is the point of the block.
 *
 * The IDE/UI acceptance asks whether the workspace, its information architecture and its wiring to
 * the real judge behave. Whether the run ENVIRONMENT is on is a different question, owned by
 * SECURITY_S0 and not by this UI: refusing learner code with 503 `code_execution_unavailable` is
 * the expected production state and does NOT fail the UI checks. Reporting the two as one number is
 * how a run could read `REAL_RUN=FAIL` beside a full IDE pass and look self-contradictory; the
 * environment state is named on its own line so the two can never be conflated again.
 */
const ideAcceptance = failed.length
  ? `FAIL (${failed.length} of ${results.length} checks: ${failed.map((entry) => entry.name).join('; ')})`
  : `PASS (${results.length}/${results.length} checks)`;

console.log('\n--- verdict (two independent results) ---');
console.log(`IDE_UI_ACCEPTANCE = ${ideAcceptance}`);
console.log(`SECURE_CODE_EXECUTION = ${codeExecutionState}` + (codeExecutionState === 'UNAVAILABLE'
  ? '  (SECURITY_S0 fail-closed; the judge refused cleanly — expected in production, not a failure)'
  : codeExecutionState === 'AVAILABLE'
    ? '  (a sandbox is active; the judge returned a real verdict)'
    : '  (no run response was seen — the UI check above failed)'));
console.log(`ONLINE_ACCEPTANCE_READY = ${failed.length ? 'NO' : codeExecutionState === 'UNKNOWN' ? 'NO' : 'YES (for the IDE / UI; secure code execution is ' + codeExecutionState + ')'}`);
console.log(`Screenshots: ${SHOTS}/`);
process.exit(failed.length ? 1 : 0);
