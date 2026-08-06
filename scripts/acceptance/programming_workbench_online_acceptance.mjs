#!/usr/bin/env node

/**
 * Resumable, UI-only Workbench acceptance runner.
 *
 * This script deliberately drives the rendered page. It does not call the
 * programming APIs to perform acceptance, and it never writes storage state,
 * cookies, response bodies, or source code into reports.
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const DEFAULT_BASE_URL = "http://101.32.190.42/";
const DEFAULT_REPORT_DIR = path.join(PROJECT_ROOT, "verification-results");
const DEFAULT_SCREENSHOT_DIR = path.join(PROJECT_ROOT, "verification-screenshots", "programming-workbench-random-40");
const DEFAULT_TRACE_DIR = path.join(PROJECT_ROOT, "verification-traces", "programming-workbench-random-40");
const DEFAULT_AUTH_STATE = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const REPORT_NAME = "programming-workbench-cli-acceptance.json";
const AUTH_REPORT_NAME = "programming-workbench-auth-bootstrap.json";
const MARKER = "/* acceptance probe: reversible UI save check */";

const GROUPS = {
  "java-blocking": [1546, 1549, 1556],
  "java-multifile": [1551, 1552, 1554, 1660, 1661, 1662, 1663, 1664],
  "java-other": [1775, 1795, 1809],
  cpp: [1734, 1756, 1758, 1762, 1767],
  python: [1629, 1819, 1822, 1833, 1845, 1846, 1847, 1849, 1865, 1866],
};

const argv = process.argv.slice(2);
function readArg(name, fallback = "") {
  const index = argv.indexOf(name);
  return index >= 0 && argv[index + 1] ? argv[index + 1] : fallback;
}
function hasFlag(name) { return argv.includes(name); }

const options = {
  baseUrl: readArg("--base-url", DEFAULT_BASE_URL),
  language: readArg("--language", ""),
  exercise: readArg("--exercise", ""),
  group: readArg("--group", ""),
  resume: hasFlag("--resume"),
  headed: (hasFlag("--headed") || hasFlag("--headed-login")) && !hasFlag("--headless"),
  storageState: path.resolve(readArg("--auth-state", readArg("--storage-state", DEFAULT_AUTH_STATE))),
  authCheckOnly: hasFlag("--auth-check-only"),
  openOnly: hasFlag("--open-only"),
  bootstrapAuth: hasFlag("--bootstrap-auth"),
  reportDir: path.resolve(readArg("--report-dir", DEFAULT_REPORT_DIR)),
  screenshotDir: path.resolve(readArg("--screenshot-dir", DEFAULT_SCREENSHOT_DIR)),
  trace: hasFlag("--trace"),
  implementationMap: readArg("--implementation-map", ""),
};
let activeReport = null;

function ensureDir(dir) { fs.mkdirSync(dir, { recursive: true }); }
function safeReadJson(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch { return fallback; }
}
function cleanText(value) { return String(value || "").replace(/\s+/g, "").trim(); }
function safeUrl(value) {
  try {
    const url = new URL(value);
    for (const key of ["username", "token", "access_token", "authorization"]) {
      if (url.searchParams.has(key)) url.searchParams.set(key, "<redacted>");
    }
    return url.toString();
  } catch { return String(value || "").replace(/(token|authorization|access_token)=[^&\s]+/gi, "$1=<redacted>"); }
}
function now() { return new Date().toISOString(); }

if (options.bootstrapAuth) {
  const bootstrapScript = path.join(SCRIPT_DIR, "programming_workbench_login_bootstrap.mjs");
  const result = spawnSync(process.execPath, [bootstrapScript, "--base-url", options.baseUrl, "--auth-state", options.storageState], { stdio: "inherit" });
  process.exit(result.status == null ? 20 : result.status);
}

function loadTitleManifest() {
  const files = [
    path.join(PROJECT_ROOT, "verification-results", "programming-workbench-random-40-sample.json"),
    path.join(PROJECT_ROOT, "verification-results", "programming-workbench-random-40-audit.json"),
    path.join(PROJECT_ROOT, "verification-results", "programming-run-test-submit-audit.json"),
  ];
  const byId = new Map();
  for (const file of files) {
    const data = safeReadJson(file, {});
    for (const item of [...(data.exercises || []), ...(data.results || []), ...(data.new_confirmed_web_records || [])]) {
      if (item.exercise_id && (item.title || item.language)) {
        const previous = byId.get(Number(item.exercise_id)) || {};
        byId.set(Number(item.exercise_id), {
          id: Number(item.exercise_id),
          language: previous.language || item.language || "",
          title: item.title || previous.title || "",
        });
      }
    }
  }
  return byId;
}

function buildTargets() {
  const titleMap = loadTitleManifest();
  let ids = [];
  if (options.exercise) ids = options.exercise.split(",").map((value) => Number(value.trim())).filter(Number.isInteger);
  else if (options.group) ids = GROUPS[options.group] || [];
  else ids = [...titleMap.keys()];
  if (options.language) {
    const normalized = options.language.toLowerCase().replace("cpp", "c++");
    ids = ids.filter((id) => String(titleMap.get(id)?.language || "").toLowerCase().replace("cpp", "c++") === normalized);
  }
  return ids.map((id) => ({ id, language: titleMap.get(id)?.language || options.language || "", title: titleMap.get(id)?.title || "" }));
}

function reportPath() { return path.join(options.reportDir, REPORT_NAME); }
function markdownPath() { return path.join(options.reportDir, REPORT_NAME.replace(/\.json$/, ".md")); }
function initialReport(targets) {
  return {
    audit: "programming-workbench-cli-acceptance",
    base_url: options.baseUrl,
    browser_surface: "Playwright CLI",
    generated_at: now(),
    options: {
      language: options.language || null,
      exercise: options.exercise || null,
      group: options.group || null,
      headed: options.headed,
      trace_enabled: options.trace,
      storage_state_supplied: Boolean(options.storageState),
      auth_state_path: path.relative(PROJECT_ROOT, options.storageState).replaceAll("\\", "/"),
      auth_check_only: options.authCheckOnly,
      open_only: options.openOnly,
      implementation_map_supplied: Boolean(options.implementationMap),
    },
    policy: {
      ui_only_acceptance: true,
      networkidle_used: false,
      telemetry_blocked: true,
      storage_state_written_to_report: false,
      response_bodies_written_to_report: false,
    },
    targets,
    records: {},
    totals: { passed: 0, failed: 0, incomplete: targets.length },
    status: "in_progress",
  };
}

function writeReport(report) {
  ensureDir(options.reportDir);
  report.generated_at = now();
  const values = Object.values(report.records);
  report.totals = {
    passed: values.filter((item) => item.final_status === "passed").length,
    failed: values.filter((item) => item.final_status === "failed").length,
    incomplete: values.filter((item) => !["passed", "failed"].includes(item.final_status)).length,
  };
  fs.writeFileSync(reportPath(), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  const lines = [
    "# Workbench CLI 线上验收",
    "",
    `- 站点：${report.base_url}`,
    `- 状态：${report.status}`,
    `- 页面验收方式：${report.browser_surface}`,
    `- 通过：${report.totals.passed}，失败：${report.totals.failed}，未完成：${report.totals.incomplete}`,
    `- storage state：${report.options.storage_state_supplied ? "已提供（内容未写入报告）" : "未提供"}`,
    "",
    "| 语言 | exercise_id | 题名 | 状态 | 失败步骤 | 当前 URL | 截图 |",
    "|---|---:|---|---|---|---|---|",
  ];
  for (const target of report.targets) {
    const item = report.records[target.id] || { final_status: "not_started" };
    lines.push(`| ${item.language || target.language || ""} | ${target.id} | ${item.title || target.title || ""} | ${item.final_status || "not_started"} | ${(item.failure_steps || []).join("；")} | ${item.url || ""} | ${(item.screenshots || []).join("、")} |`);
  }
  fs.writeFileSync(markdownPath(), `${lines.join("\n")}\n`, "utf8");
}

function loadOrCreateReport(targets) {
  if (options.resume && fs.existsSync(reportPath())) {
    const report = safeReadJson(reportPath(), null);
    if (report?.audit === "programming-workbench-cli-acceptance") {
      report.options = {
        ...report.options,
        language: options.language || null,
        exercise: options.exercise || null,
        group: options.group || null,
        headed: options.headed,
        trace_enabled: options.trace,
        storage_state_supplied: Boolean(options.storageState),
        implementation_map_supplied: Boolean(options.implementationMap),
      };
      for (const target of targets) {
        const existingTarget = report.targets.find((item) => item.id === target.id);
        if (existingTarget) {
          existingTarget.language = target.language || existingTarget.language || "";
          existingTarget.title = target.title || existingTarget.title || "";
          if (report.records[target.id]) {
            report.records[target.id].language = existingTarget.language;
            report.records[target.id].title = existingTarget.title;
          }
        } else report.targets.push(target);
      }
      return report;
    }
  }
  return initialReport(targets);
}

function telemetryUrl(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host.includes("statsig") || host === "ab.chatgpt.com" || host.includes("analytics") || host.includes("telemetry") || host.includes("featuregates");
  } catch { return false; }
}

function buildRecord(target) {
  return {
    exercise_id: target.id,
    language: target.language,
    title: target.title,
    final_status: "in_progress",
    url: "",
    steps: {},
    failure_steps: [],
    screenshots: [],
    traces: [],
    console_errors: [],
    websocket_events: [],
    business_responses: [],
    hidden_leakage: false,
    networkidle_used: false,
  };
}

function authReportPath() { return path.join(options.reportDir, AUTH_REPORT_NAME); }

function writeAuthCheckReport(result) {
  ensureDir(options.reportDir);
  const existing = safeReadJson(authReportPath(), {});
  const report = {
    ...existing,
    audit: "programming-workbench-auth-bootstrap",
    generated_at: now(),
    origin: new URL(options.baseUrl).origin,
    storage_state_path: path.relative(PROJECT_ROOT, options.storageState).replaceAll("\\", "/"),
    status: result.status,
    authentication: {
      ...(existing.authentication || {}),
      ...(result.authentication || {}),
    },
    validation: result.validation || null,
    auth_state_valid: result.validation?.auth_state_valid === true || existing.auth_state_valid === true,
    auth_probe: result.validation?.auth_probe || existing.auth_probe || "not_verified",
    policy: {
      ...(existing.policy || {}),
      sensitive_values_written: false,
      cookies_written_to_report: false,
    },
    error: result.error || undefined,
  };
  fs.writeFileSync(authReportPath(), `${JSON.stringify(report, null, 2)}\n`, "utf8");
  const markdown = [
    "# Workbench 登录态引导验收",
    "",
    `- origin：${report.origin}`,
    `- 状态：${report.status}`,
    `- storageState：${report.storage_state_path}`,
    `- Cookie 数量：${report.authentication.cookie_count ?? "未读取"}`,
    `- localStorage key：${(report.authentication.local_storage_keys || []).join(", ") || "未读取"}`,
    `- 用户标识（脱敏）：${report.authentication.redacted_identity || "未读取"}`,
    `- /api/me 状态：${report.authentication.me_status ?? "未调用"}`,
    `- auth_state_valid：${report.auth_state_valid === true ? "true" : "false"}`,
    `- auth_probe：${report.auth_probe || "未执行"}`,
    `- 认证验证：${report.validation?.status || "未执行"}`,
    report.error ? `- 错误：${report.error}` : "- 敏感值未写入报告。",
  ].join("\n");
  fs.writeFileSync(path.join(options.reportDir, AUTH_REPORT_NAME.replace(/\.json$/, ".md")), `${markdown}\n`, "utf8");
}

async function inspectAuthState(page) {
  return page.evaluate(async () => {
    const raw = localStorage.getItem("ai_study_platform_user");
    let user = null;
    try { user = raw ? JSON.parse(raw) : null; } catch { user = null; }
    const username = typeof user?.username === "string" ? user.username : "";
    let meStatus = null;
    if (username) {
      try {
        const response = await fetch("/api/me", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username }) });
        meStatus = response.status;
      } catch { meStatus = "network_error"; }
    }
    return {
      has_user: Boolean(username),
      username,
      me_status: meStatus,
      local_storage_keys: Object.keys(localStorage),
      nav_count: document.querySelectorAll(".ph-nav button").length,
      workbench: Boolean(document.querySelector(".pw-shell")),
      login_form: Boolean(document.querySelector("input[type='password']")),
      url: location.href,
    };
  });
}

function maskIdentity(value) {
  const text = String(value || "");
  if (!text) return "";
  if (text.length <= 2) return `${text[0]}*`;
  return `${text.slice(0, 1)}${"*".repeat(Math.min(6, text.length - 2))}${text.slice(-1)}`;
}

async function runAuthCheck() {
  const result = { status: "failed", authentication: {}, validation: { status: "not_verified" } };
  if (!options.storageState || !fs.existsSync(options.storageState)) {
    result.error = `AUTH_STATE_MISSING: ${path.relative(PROJECT_ROOT, options.storageState || DEFAULT_AUTH_STATE).replaceAll("\\", "/")}`;
    writeAuthCheckReport(result);
    console.error(result.error);
    return false;
  }
  let browser;
  let context;
  try {
    const state = safeReadJson(options.storageState, null);
    const origin = new URL(options.baseUrl).origin;
    const stateOrigins = (state?.origins || []).map((item) => item.origin);
    const cookieCount = Array.isArray(state?.cookies) ? state.cookies.length : 0;
    if (!state || !stateOrigins.includes(origin)) throw Object.assign(new Error("AUTH_STATE_EXPIRED: formal site origin missing from storageState"), { code: "auth_state_expired" });
    browser = await chromium.launch({ headless: !options.headed });
    context = await browser.newContext({ storageState: options.storageState, viewport: { width: 1366, height: 768 } });
    await context.route("**/*", async (route) => telemetryUrl(route.request().url()) ? route.abort() : route.continue());
    const page = await context.newPage();
    await page.goto(options.baseUrl, { waitUntil: "domcontentloaded", timeout: 45_000 });
    let snapshot = await inspectAuthState(page);
    if (!snapshot.has_user || snapshot.me_status !== 200) {
      throw Object.assign(new Error(`AUTH_STATE_EXPIRED: /api/me status=${snapshot.me_status ?? "missing"}`), { code: "auth_state_expired" });
    }
    result.authentication = {
      cookie_count: cookieCount,
      local_storage_keys: snapshot.local_storage_keys,
      redacted_identity: maskIdentity(snapshot.username),
      me_status: snapshot.me_status,
      origin_in_storage_state: true,
    };
    if (snapshot.login_form) {
      throw Object.assign(new Error(`LOGIN_REDIRECT: url=${snapshot.url}`), { code: "login_redirect" });
    }
    result.validation = {
      status: "passed",
      auth_state_valid: true,
      auth_probe: "passed",
      auth_only: true,
      login_form_visible: false,
      current_url: page.url(),
    };
    result.status = "passed";
    writeAuthCheckReport(result);
    console.log("AUTH_CHECK_PASSED");
    console.log("Authentication state is valid.");
    return true;
  } catch (error) {
    result.error = `${error?.code || "business_request_failed"}: ${String(error?.message || error).slice(0, 600)}`;
    result.validation = { status: "failed", category: error?.code || "business_request_failed" };
    writeAuthCheckReport(result);
    console.error(`AUTH_CHECK_FAILED ${result.error}`);
    return false;
  } finally {
    if (context) await context.close().catch(() => {});
    if (browser) await browser.close().catch(() => {});
  }
}

function createUiContext(browser, record) {
  const contextOptions = { viewport: { width: 1366, height: 768 } };
  if (options.storageState) contextOptions.storageState = options.storageState;
  return browser.newContext(contextOptions).then(async (context) => {
    await context.route("**/*", async (route) => {
      const requestUrl = route.request().url();
      if (telemetryUrl(requestUrl)) return route.abort();
      return route.continue();
    });
    const page = await context.newPage();
    if (options.trace) {
      await context.tracing.start({ screenshots: true, snapshots: true, title: `exercise-${record.exercise_id}` });
    }
    page.on("console", (message) => {
      if (["error", "warning"].includes(message.type())) record.console_errors.push({ type: message.type(), text: String(message.text()).slice(0, 500) });
    });
    page.on("pageerror", (error) => record.console_errors.push({ type: "pageerror", text: String(error.message || error).slice(0, 500) }));
    page.on("request", (request) => {
      const url = request.url();
      if (url.includes("/api/") || url.includes("/programming/") || url.includes("/code/")) {
        record.business_responses.push({ phase: "request", method: request.method(), url: safeUrl(url), at: now() });
      }
    });
    page.on("response", (response) => {
      const url = response.url();
      if (url.includes("/api/") || url.includes("/programming/") || url.includes("/code/")) {
        record.business_responses.push({ phase: "response", status: response.status(), url: safeUrl(url), at: now() });
      }
    });
    page.on("websocket", (socket) => {
      const item = { url: safeUrl(socket.url()), opened: now(), frames_sent: 0, frames_received: 0 };
      record.websocket_events.push(item);
      socket.on("framesent", () => { item.frames_sent += 1; });
      socket.on("framereceived", () => { item.frames_received += 1; });
      socket.on("close", () => { item.closed = now(); });
    });
    return { context, page };
  });
}

async function screenshot(page, record, label) {
  ensureDir(options.screenshotDir);
  const file = path.join(options.screenshotDir, `cli-${record.exercise_id}-${label}.png`);
  try { await page.screenshot({ path: file, fullPage: false }); record.screenshots.push(path.relative(PROJECT_ROOT, file).replaceAll("\\", "/")); } catch { /* keep the step failure */ }
}

async function step(page, record, name, action) {
  const entry = { started_at: now(), passed: false };
  record.steps[name] = entry;
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      entry.details = await action();
      entry.passed = true;
      entry.attempts = attempt;
      break;
    } catch (error) {
      lastError = error;
      const message = String(error?.message || error);
      entry.attempts = attempt;
      if (attempt === 1 && /timeout|timed out|exceeded/i.test(message)) {
        entry.retry_reason = message.slice(0, 500);
        await page.waitForTimeout(250);
        continue;
      }
      break;
    }
  }
  if (!entry.passed) {
    entry.error = String(lastError?.message || lastError || "step failed").slice(0, 800);
    if (!record.failure_steps.includes(name)) record.failure_steps.push(name);
    await screenshot(page, record, name.replace(/[^a-z0-9_-]+/gi, "-").slice(0, 60));
  }
  entry.finished_at = now();
  writeReport(activeReport);
  return entry.passed;
}

async function clickUnique(locator, label) {
  const count = await locator.count();
  if (count !== 1) throw new Error(`${label}: expected 1 element, got ${count}`);
  await locator.click({ timeoutMs: 12000 });
}

async function getText(locator, label) {
  const count = await locator.count();
  if (count !== 1) throw new Error(`${label}: expected 1 element, got ${count}`);
  return locator.innerText({ timeoutMs: 12000 });
}

function isExerciseListUrl(value) {
  try {
    const url = new URL(value);
    return /\/api\/programming\/exercises$/.test(url.pathname);
  } catch { return false; }
}

async function waitForLibraryResponse(page, language, pageNumber, action) {
  const expectedLanguage = cleanText(language).toLowerCase();
  const responsePromise = page.waitForResponse((response) => {
    if (response.status() !== 200 || !isExerciseListUrl(response.url())) return false;
    try {
      const url = new URL(response.url());
      return cleanText(url.searchParams.get("language")).toLowerCase() === expectedLanguage && Number(url.searchParams.get("page") || 1) === pageNumber;
    } catch { return false; }
  }, { timeout: 30_000 }).then((response) => ({
    status: response.status(),
    url: safeUrl(response.url()),
  })).catch(() => null);
  await action();
  return responsePromise;
}

async function fetchLibraryPage(page, language, pageNumber, pageSize) {
  return page.evaluate(async ({ language: selectedLanguage, pageNumber: selectedPage, pageSize: selectedPageSize }) => {
    const raw = localStorage.getItem("ai_study_platform_user");
    let user = null;
    try { user = raw ? JSON.parse(raw) : null; } catch { user = null; }
    const query = new URLSearchParams({ language: selectedLanguage, page: String(selectedPage), page_size: String(selectedPageSize) });
    if (user?.username) query.set("username", user.username);
    const response = await fetch(`/api/programming/exercises?${query.toString()}`);
    const data = await response.json().catch(() => ({}));
    return {
      status: response.status,
      total: Number(data.total || 0),
      total_pages: Number(data.total_pages || 1),
      page: Number(data.page || selectedPage),
      page_size: Number(data.page_size || selectedPageSize),
      exercises: (data.exercises || []).map((item) => ({
        id: Number(item.id),
        language: item.language || "",
        title: item.title || item.title_zh || "",
      })),
    };
  }, { language, pageNumber, pageSize });
}

async function readLibraryPageNumber(page) {
  const text = await page.locator(".ph-pagination span").innerText({ timeoutMs: 30_000 }).catch(() => "");
  const match = text.match(/第\s*(\d+)\s*\/\s*(\d+)\s*页/);
  return match ? { page: Number(match[1]), total_pages: Number(match[2]), text } : { page: null, total_pages: null, text };
}

async function chooseLibraryExercise(page, target, audit = {}) {
  audit.language = target.language || "";
  audit.target_exercise_id = Number(target.id);
  audit.search_available = false;
  audit.search_used = false;
  audit.pages_visited = [];
  audit.list_requests = [];
  const nav = page.locator(".ph-nav button");
  await nav.nth(3).waitFor({ state: "visible", timeout: 30_000 });
  const navCount = await nav.count();
  if (navCount !== 4) throw new Error(`programming navigation expected 4 buttons, got ${navCount}`);
  await nav.nth(3).click({ timeoutMs: 12000 });
  const languageButtons = page.locator(".ph-exercise-filters:not(.ph-exercise-status-filters) button");
  await languageButtons.first().waitFor({ state: "visible", timeout: 30_000 });
  const languageCount = await languageButtons.count();
  if (languageCount !== 4) throw new Error(`language filter expected 4 buttons, got ${languageCount}`);
  const labels = await languageButtons.allTextContents({ timeoutMs: 12000 });
  const language = target.language || "";
  const index = labels.findIndex((label) => cleanText(label).toLowerCase() === cleanText(language).toLowerCase());
  if (index < 0) throw new Error(`language filter not found: ${language}`);
  const canonicalLanguage = String(labels[index]).trim();
  audit.language = canonicalLanguage;
  const languageResponse = await waitForLibraryResponse(page, canonicalLanguage, 1, () => languageButtons.nth(index).click({ timeoutMs: 12000 }));
  if (languageResponse) audit.list_requests.push(languageResponse);
  const activeLanguage = await page.locator(".ph-exercise-filters button.is-active").innerText({ timeoutMs: 12000 }).catch(() => "");
  if (cleanText(activeLanguage).toLowerCase() !== cleanText(canonicalLanguage).toLowerCase()) throw new Error(`language filter did not settle on ${canonicalLanguage}`);
  const selects = page.locator(".ph-exercise-status-filters select");
  const selectCount = await selects.count();
  if (selectCount >= 3) {
    const pageSizeResponse = await waitForLibraryResponse(page, canonicalLanguage, 1, () => selects.nth(2).selectOption("48"));
    if (pageSizeResponse) audit.list_requests.push(pageSizeResponse);
  }
  const titleSearch = page.locator("input[placeholder*='搜索'], input[aria-label*='搜索']");
  audit.search_available = (await titleSearch.count()) > 0;
  let pageNumber = 1;
  let totalPages = 1;
  while (pageNumber <= totalPages) {
    const apiPage = await fetchLibraryPage(page, canonicalLanguage, pageNumber, 48);
    if (apiPage.status !== 200) throw new Error(`Java list API returned ${apiPage.status} on page ${pageNumber}`);
    totalPages = Math.max(1, apiPage.total_pages);
    const pageState = await readLibraryPageNumber(page);
    audit.pages_visited.push({ page: pageNumber, total_pages: totalPages, dom_page: pageState.page, api_total: apiPage.total, api_ids: apiPage.exercises.map((item) => item.id) });
    const targetIndex = apiPage.exercises.findIndex((item) => item.id === Number(target.id));
    const cards = page.locator(".ph-exercise-card");
    const targetCard = targetIndex >= 0 ? cards.nth(targetIndex) : null;
    if (targetCard) await targetCard.waitFor({ state: "visible", timeoutMs: 15_000 });
    const count = await cards.count();
    const texts = count ? await cards.allTextContents({ timeoutMs: 12_000 }) : [];
    if (targetIndex >= 0) {
      if (targetIndex >= count) throw new Error(`target ${target.id} is in API page ${pageNumber} but its UI card is not rendered`);
      const card = cards.nth(targetIndex);
      const cardText = texts[targetIndex] || "";
      const apiTarget = apiPage.exercises[targetIndex];
      const expectedTitle = cleanText(apiTarget.title || target.title);
      if (!expectedTitle || !cleanText(cardText).includes(expectedTitle)) throw new Error(`target ${target.id} card title did not match API title`);
      const startButton = card.locator("button");
      const buttonCount = await startButton.count();
      if (buttonCount < 1) throw new Error("exercise card has no start button");
      audit.search_used = false;
      await startButton.nth(buttonCount - 1).click({ timeoutMs: 15_000 });
      audit.found_by = "api_page_index_then_exact_title_card";
      audit.found_page = pageNumber;
      audit.found_title = apiTarget.title;
      return { page: pageNumber, card_text: cardText.slice(0, 800), api_target: apiTarget, audit };
    }
    if (pageNumber >= totalPages) break;
    const pagingButtons = page.locator(".ph-pagination button");
    const pagingCount = await pagingButtons.count();
    if (pagingCount !== 2 || !(await pagingButtons.nth(1).isEnabled())) break;
    pageNumber += 1;
    const nextResponse = await waitForLibraryResponse(page, canonicalLanguage, pageNumber, () => pagingButtons.nth(1).click({ timeoutMs: 12_000 }));
    if (nextResponse) audit.list_requests.push(nextResponse);
  }
  throw new Error(`exercise card not found in Java approved library: ${target.id} ${target.title}`);
}

async function verifyWorkbenchIdentity(page, target, record) {
  const shell = page.locator(".pw-shell");
  await shell.waitFor({ state: "visible", timeout: 30_000 });
  const titleLocator = page.locator(".pw-exercise-sidebar h1");
  await titleLocator.waitFor({ state: "visible", timeout: 30_000 });
  const title = await getText(titleLocator, "Workbench exercise title");
  const detail = await page.evaluate(async (exerciseId) => {
    const response = await fetch(`/api/programming/exercises/${exerciseId}`);
    const data = await response.json().catch(() => ({}));
    const exercise = data.exercise || data;
    return { status: response.status, id: Number(exercise?.id || 0), language: exercise?.language || "", title: exercise?.title || exercise?.title_zh || "" };
  }, Number(target.id));
  if (detail.status !== 200 || detail.id !== Number(target.id)) throw new Error(`Workbench detail identity mismatch: expected ${target.id}, got ${detail.id || detail.status}`);
  if (cleanText(detail.language).toLowerCase() !== cleanText(target.language).toLowerCase()) throw new Error(`Workbench language mismatch: expected ${target.language}, got ${detail.language}`);
  if (!cleanText(title).includes(cleanText(detail.title || target.title))) throw new Error(`Workbench title mismatch for exercise ${target.id}`);
  record.workbench_identity = { exercise_id: detail.id, language: detail.language, title: detail.title, page_url: page.url() };
  return record.workbench_identity;
}

async function inspectWorkbench(page, record) {
  const shell = page.locator(".pw-shell");
  if (await shell.count() !== 1) throw new Error("Workbench shell not rendered");
  const title = await getText(page.locator(".pw-exercise-sidebar h1"), "exercise title");
  const statementCount = await page.locator(".pw-exercise-statement-copy").count();
  const sampleCount = await page.locator(".pw-exercise-example-card").count();
  const editor = page.locator(".pw-editor-card .monaco-editor");
  await editor.waitFor({ state: "visible", timeoutMs: 30_000 });
  const editorCount = await editor.count();
  if (statementCount !== 1 || sampleCount < 3 || editorCount !== 1) throw new Error(`workbench content incomplete: statement=${statementCount}, samples=${sampleCount}, editor=${editorCount}`);
  const snapshot = await page.locator(".pw-exercise-sidebar").innerText({ timeoutMs: 12000 });
  record.hidden_leakage = /reference_solution|reference_files|hidden_cases|hidden_tests/i.test(snapshot);
  if (record.hidden_leakage) throw new Error("hidden/reference content appeared in visible Workbench");
  const fileTabs = page.locator(".pw-file-tabs button");
  const fileCount = await fileTabs.count();
  return { title: title.slice(0, 300), file_count: fileCount, public_sample_count: sampleCount, hidden_leakage: false };
}

async function inspectJavaFiles(page, record) {
  const trigger = page.locator(".pw-file-list-trigger");
  if (await trigger.count() !== 1) return { multifile: false };
  await clickUnique(trigger, "Java file list trigger");
  const popover = page.locator(".pw-file-list-popover");
  if (await popover.count() !== 1) throw new Error("Java file list popover did not open");
  const files = popover.locator("button");
  const count = await files.count();
  if (count < 3) throw new Error(`expected at least 3 editable Java files, got ${count}`);
  const names = await files.allTextContents({ timeoutMs: 12000 });
  const scroll = await popover.evaluate((node) => ({ scrollHeight: node.scrollHeight, clientHeight: node.clientHeight, overflowY: getComputedStyle(node).overflowY }));
  if (scroll.scrollHeight > scroll.clientHeight && !["auto", "scroll"].includes(scroll.overflowY)) throw new Error("Java file list cannot scroll");
  await files.nth(count - 1).click({ timeoutMs: 12000 });
  await page.waitForTimeout(350);
  const activeTab = page.locator(".pw-file-tab.is-active");
  const activeName = await getText(activeTab, "last Java file active tab");
  record.java_multifile = { file_count: count, files: names.map((item) => item.trim()).filter(Boolean), scroll, last_file_reached: true, active_file: activeName.slice(0, 200) };
  return record.java_multifile;
}

async function inspectMonaco(page) {
  await page.locator(".pw-editor-card .monaco-editor").waitFor({ state: "visible", timeoutMs: 30_000 });
  const result = await page.evaluate(() => {
    const models = globalThis.monaco?.editor?.getModels?.() || [];
    return {
      monaco_api_available: models.length > 0,
      models: models.map((model) => ({ uri: String(model.uri), line_count: model.getLineCount(), value_length: model.getValue().length })),
      visible_line_nodes: document.querySelectorAll(".monaco-editor .view-lines .view-line").length,
      todo_visible: document.querySelector(".monaco-editor")?.textContent?.includes("TODO") || false,
    };
  });
  if (!result.monaco_api_available && !result.visible_line_nodes) throw new Error("Monaco model or visible editor lines unavailable");
  return result;
}

async function runInteractive(page, target, record) {
  const fileTrigger = page.locator(".pw-file-list-trigger");
  if (await fileTrigger.count() === 1) {
    await clickUnique(fileTrigger, "entry file list trigger");
    const fileButtons = page.locator(".pw-file-list-popover button");
    const fileCount = await fileButtons.count();
    let entryIndex = -1;
    for (let index = 0; index < fileCount; index += 1) {
      const title = await fileButtons.nth(index).getAttribute("title", { timeoutMs: 12000 });
      const text = await fileButtons.nth(index).innerText({ timeoutMs: 12000 }).catch(() => "");
      if (/Main\.java|main\.cpp|main\.py/i.test(`${title || ""} ${text}`)) { entryIndex = index; break; }
    }
    if (entryIndex >= 0) {
      await fileButtons.nth(entryIndex).click({ timeoutMs: 12000 });
      await page.waitForTimeout(700);
    }
  }
  const run = page.locator("button[data-action='top-run']");
  await clickUnique(run, "Run");
  await page.waitForTimeout(1200);
  const terminal = page.locator(".pw-xterm");
  if (await terminal.count() !== 1) throw new Error("terminal not rendered after Run");
  // Read the first sample's input from its protocol code block. This avoids
  // relying on localized rendered labels, which may be mojibake in old builds.
  const sampleCards = page.locator(".pw-exercise-example-card");
  const sampleCardCount = await sampleCards.count();
  if (!sampleCardCount) throw new Error("no public sample card available for interactive run");
  const sampleCodeBlocks = sampleCards.nth(0).locator("code");
  const sampleCodeCount = await sampleCodeBlocks.count();
  const stableSampleInput = sampleCodeCount >= 1 ? await sampleCodeBlocks.nth(0).innerText({ timeoutMs: 12000 }) : "";
  const sendSample = sampleCards.nth(0).locator(".pw-send-sample-input");
  const sendSampleCount = await sendSample.count();
  let stableInputSent = false;
  let stableEofSent = false;
  if (sendSampleCount === 1) {
    await sendSample.click({ timeoutMs: 12000 });
    stableInputSent = true;
    const eofButton = page.locator(".pw-terminal-input-actions button").filter({ hasText: "发送 EOF" });
    try {
      await eofButton.waitFor({ state: "visible", timeoutMs: 12000 });
      await eofButton.click({ timeoutMs: 12000 });
      stableEofSent = true;
    } catch (error) {
      record.interactive_run = {
        input_sent: stableInputSent,
        eof_sent: false,
        exit_observed: false,
        output_excerpt: "",
        failure_reason: `EOF control was not available after sending the sample: ${String(error?.message || error).slice(0, 300)}`,
      };
      throw new Error(record.interactive_run.failure_reason);
    }
  }
  if (!stableInputSent && stableSampleInput.trim()) {
    await terminal.click({ timeoutMs: 12000 });
    await page.keyboard.type(stableSampleInput.trimEnd());
    await page.keyboard.press("Enter");
    await page.keyboard.press("Control+D");
  }
  const finishedStatus = page.locator(".pw-terminal-status").filter({ hasText: "运行结束" });
  try {
    await finishedStatus.waitFor({ state: "visible", timeoutMs: 12000 });
  } catch {
    await page.waitForTimeout(500);
  }
  const runDetailsToggle = page.locator("button.pw-run-details-toggle");
  if (await runDetailsToggle.count() === 1) await runDetailsToggle.click({ timeoutMs: 12000 });
  const stableResultText = await page.locator(".pw-run-result").innerText({ timeoutMs: 12000 }).catch(() => "");
  const stableBodyText = await page.locator(".pw-bottom-toolwindow").innerText({ timeoutMs: 12000 }).catch(() => "");
  const stableCombinedText = `${stableResultText}\n${stableBodyText}`;
  const stableHasExit = /退出码|exit(?:[_ -]?code)?|程序已结束|进程已结束|process\s+exited/i.test(stableCombinedText);
  record.interactive_run = {
    input_sent: stableInputSent || Boolean(stableSampleInput.trim()),
    eof_sent: stableEofSent,
    exit_observed: stableHasExit,
    output_excerpt: stableResultText.slice(0, 600),
  };
  if (!stableHasExit) throw new Error("Run did not expose an exit state within bounded wait");
  return record.interactive_run;

  const sample = page.locator(".pw-exercise-example-card");
  const sampleText = await sample.nth(0).innerText({ timeoutMs: 12000 });
  const inputMatch = sampleText.match(/(?:输入|杈撳叆)\s*([\s\S]*?)(?:标准输出|鏍囧噯杈撳嚭)/i);
  if (inputMatch?.[1]?.trim()) {
    await terminal.click({ timeoutMs: 12000 });
    await page.keyboard.insertText(inputMatch[1].trimEnd() + "\n");
  }
  await page.waitForTimeout(5000);
  const resultText = await page.locator(".pw-run-result").innerText({ timeoutMs: 12000 }).catch(() => "");
  const body = await page.locator(".pw-bottom-toolwindow").innerText({ timeoutMs: 12000 }).catch(() => "");
  const hasExit = /退出码|exit|进程结束|杩涚▼缁撳束/i.test(`${resultText}\n${body}`);
  record.interactive_run = { input_sent: Boolean(inputMatch?.[1]?.trim()), exit_observed: hasExit, output_excerpt: resultText.slice(0, 600) };
  if (!hasExit) throw new Error("Run did not expose an exit state within bounded wait");
  return record.interactive_run;
}

async function runPublicTest(page, record) {
  const stableTest = page.locator("button.pw-top-exercise-action:not(.pw-top-exercise-action--primary):not(.pw-file-list-trigger)");
  await clickUnique(stableTest, "Test");
  const stablePicker = page.locator("section.pw-test-picker");
  if (await stablePicker.count() !== 1) throw new Error("public test picker did not open");
  const stableCheckboxes = stablePicker.locator("input[type='checkbox']");
  const stableCount = await stableCheckboxes.count();
  if (stableCount < 3) throw new Error(`public test picker expected at least 3 cases, got ${stableCount}`);
  await clickUnique(stablePicker.locator("button.pw-top-exercise-action--primary"), "start public tests");
  await stablePicker.waitFor({ state: "hidden", timeoutMs: 30000 });
  const stableModal = page.locator("section.pw-result-modal:not(.pw-test-picker)");
  await stableModal.waitFor({ state: "visible", timeoutMs: 30000 });
  const stableText = await stableModal.innerText({ timeoutMs: 12000 });
  const stableSummary = stableModal.locator(".pw-result-modal-summary strong");
  const stableSummaryText = await stableSummary.count() === 1 ? await stableSummary.innerText({ timeoutMs: 12000 }) : "";
  const stableMatch = `${stableSummaryText} ${stableText}`.match(/(\d+)\s*[\/／]\s*(\d+)/);
  record.public_test = { picker_case_count: stableCount, summary: stableMatch ? `${stableMatch[1]}/${stableMatch[2]}` : "not_parsed", summary_text: stableSummaryText.slice(0, 120), modal_text_excerpt: stableText.slice(0, 300), hidden_visible: /reference_solution|reference_files|hidden_cases|hidden_tests/i.test(stableText) };
  if (record.public_test.hidden_visible) throw new Error("hidden test detail appeared in public test modal");
  return record.public_test;
  const test = page.locator("button.pw-top-exercise-action").filter({ hasText: "测试" });
  await clickUnique(test, "Test");
  const picker = page.locator("section.pw-test-picker");
  if (await picker.count() !== 1) throw new Error("public test picker did not open");
  const checkboxes = picker.locator("input[type='checkbox']");
  const count = await checkboxes.count();
  if (count < 3) throw new Error(`public test picker expected at least 3 cases, got ${count}`);
  const begin = picker.locator("button").filter({ hasText: "开始测试" });
  await clickUnique(begin, "start public tests");
  const modal = page.locator("section.pw-result-modal");
  await modal.waitFor({ state: "visible", timeoutMs: 30000 });
  const text = await modal.innerText({ timeoutMs: 12000 });
  const match = text.match(/(?:通过|閫氳繃)\s*(\d+)\s*\/\s*(\d+)/);
  record.public_test = { picker_case_count: count, summary: match ? `${match[1]}/${match[2]}` : "not_parsed", hidden_visible: /hidden_cases|hidden_tests|隐藏输入|隐藏测试源码/i.test(text) };
  if (record.public_test.hidden_visible) throw new Error("hidden test detail appeared in public test modal");
  return record.public_test;
}

async function runSubmit(page, record) {
  const stableModal = page.locator("section.pw-result-modal");
  const stableClose = stableModal.locator("button.pw-modal-close");
  if (await stableClose.count() === 1) await stableClose.click({ timeoutMs: 12000 });
  await clickUnique(page.locator("button.pw-top-exercise-action--primary"), "Submit");
  await stableModal.waitFor({ state: "visible", timeoutMs: 45000 });
  const stableText = await stableModal.innerText({ timeoutMs: 12000 });
  const stableSummary = stableModal.locator(".pw-result-modal-summary strong");
  const stableSummaryText = await stableSummary.count() === 1 ? await stableSummary.innerText({ timeoutMs: 12000 }) : "";
  const stableMatch = `${stableSummaryText} ${stableText}`.match(/(\d+)\s*[\/／]\s*(\d+)/);
  record.submit = { summary: stableMatch ? `${stableMatch[1]}/${stableMatch[2]}` : "not_parsed", summary_text: stableSummaryText.slice(0, 120), modal_text_excerpt: stableText.slice(0, 300), hidden_visible: /reference_solution|reference_files|hidden_cases|hidden_tests/i.test(stableText) };
  if (record.submit.hidden_visible) throw new Error("hidden test detail appeared in submit modal");
  return record.submit;
  const modal = page.locator("section.pw-result-modal");
  const close = modal.locator("button[aria-label='关闭']");
  if (await close.count() === 1) await close.click({ timeoutMs: 12000 });
  const submit = page.locator("button.pw-top-exercise-action--primary");
  await clickUnique(submit, "Submit");
  await modal.waitFor({ state: "visible", timeoutMs: 45000 });
  const text = await modal.innerText({ timeoutMs: 12000 });
  const match = text.match(/(?:通过|閫氳繃)\s*(\d+)\s*\/\s*(\d+)/);
  record.submit = { summary: match ? `${match[1]}/${match[2]}` : "not_parsed", hidden_visible: /hidden_cases|hidden_tests|隐藏输入|隐藏测试源码/i.test(text) };
  if (record.submit.hidden_visible) throw new Error("hidden test detail appeared in submit modal");
  return record.submit;
}

async function cleanTopicSwitch(page, record) {
  const openModal = page.locator("section.pw-result-modal");
  const closeModal = openModal.locator("button.pw-modal-close");
  if (await closeModal.count() === 1) await closeModal.click({ timeoutMs: 12000 });
  const nav = page.locator(".ph-nav button");
  const count = await nav.count();
  if (count !== 4) throw new Error(`navigation disappeared after Workbench: ${count}`);
  await nav.nth(3).click({ timeoutMs: 12000 });
  await page.waitForTimeout(350);
  const workbench = page.locator(".pw-shell");
  if (await workbench.count() !== 0) throw new Error("old Workbench remained after switching to library");
  record.clean_topic_switch = true;
  return true;
}

async function loadAuditedImplementation(target) {
  if (!options.implementationMap) return null;
  const map = safeReadJson(path.resolve(options.implementationMap), {});
  const entries = Object.values(map).filter((item) => Number(item.exercise_id) === target.id);
  if (!entries.length) return null;
  return entries[0].reference_files || null;
}

async function applyAuditedImplementation(page, target, record) {
  const files = await loadAuditedImplementation(target);
  if (!Array.isArray(files) || !files.length) return { applied: false };
  const fileList = page.locator(".pw-file-list-popover button");
  let count = await fileList.count();
  if (!count) {
    const trigger = page.locator(".pw-file-list-trigger");
    if (await trigger.count() === 1) {
      await trigger.click({ timeoutMs: 12000 });
      count = await fileList.count();
    }
  }
  const applied = [];
  if (count) {
    for (let index = 0; index < count; index += 1) {
      if (index > 0) {
        const trigger = page.locator(".pw-file-list-trigger");
        await clickUnique(trigger, "Java file list trigger");
        await page.locator(".pw-file-list-popover").waitFor({ state: "visible", timeoutMs: 12000 });
      }
      const currentFileList = page.locator(".pw-file-list-popover button");
      const button = currentFileList.nth(index);
      const filePath = await button.getAttribute("title", { timeoutMs: 12000 });
      const buttonText = await button.innerText({ timeoutMs: 12000 }).catch(() => "");
      const fileIdentity = `${filePath || ""} ${buttonText || ""}`.replace(/\s+/g, "");
      const implementation = files.find((item) => fileIdentity.includes(String(item.path).replace(/\s+/g, "")) || (filePath && (item.path === filePath || filePath.endsWith(`/${item.path}`) || filePath.endsWith(item.path))));
      if (!implementation) continue;
      await button.click({ timeoutMs: 12000 });
      await page.locator(".pw-editor-card .monaco-editor").waitFor({ state: "visible", timeoutMs: 30000 });
      await page.waitForTimeout(700);
      await page.evaluate(({ expectedPath, content }) => {
        const models = globalThis.monaco?.editor?.getModels?.() || [];
        const normalize = (value) => decodeURIComponent(String(value || "")).replace(/\\/g, "/");
        const model = models.find((item) => normalize(item.uri?.path).endsWith(expectedPath) || normalize(item.uri).endsWith(expectedPath)) || (models.length === 1 ? models[0] : null);
        if (!model) throw new Error(`Monaco model not found for ${expectedPath}`);
        model.setValue(content || "");
      }, { expectedPath: implementation.path, content: implementation.content });
      applied.push(implementation.path);
      await page.waitForTimeout(900);
    }
  } else {
    const implementation = files[0];
    await page.waitForTimeout(700);
    await page.evaluate(({ expectedPath, content }) => {
      const models = globalThis.monaco?.editor?.getModels?.() || [];
      const normalize = (value) => decodeURIComponent(String(value || "")).replace(/\\/g, "/");
      const model = models.find((item) => normalize(item.uri?.path).endsWith(expectedPath) || normalize(item.uri).endsWith(expectedPath)) || (models.length === 1 ? models[0] : null);
      if (!model) throw new Error(`Monaco model not found for ${expectedPath}`);
      model.setValue(content || "");
    }, { expectedPath: implementation.path, content: implementation.content });
    applied.push(implementation.path);
  }
  record.implementation_applied = { file_count: applied.length, paths: applied };
  await page.waitForTimeout(1200);
  return record.implementation_applied;
}

async function runTarget(browser, target) {
  const record = activeReport.records[target.id] || buildRecord(target);
  activeReport.records[target.id] = record;
  record.failure_steps = [];
  record.steps = {};
  record.final_status = "in_progress";
  delete record.top_level_error;
  delete record.failure_category;
  delete record.open_only;
  delete record.workbench_identity;
  delete record.library_probe;
  record.screenshots = [];
  record.traces = [];
  record.console_errors = [];
  record.websocket_events = [];
  record.business_responses = [];
  let context;
  let page;
  try {
    ({ context, page } = await createUiContext(browser, record));
    await step(page, record, "open_site", async () => {
      await page.goto(options.baseUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
      await page.waitForTimeout(1200);
      record.url = page.url();
      record.page_title = await page.title();
      const snapshot = await page.locator("body").innerText({ timeoutMs: 12000 });
      if (!snapshot.trim()) throw new Error("blank page");
      return { url: record.url, title: record.page_title, visible_chars: snapshot.length };
    });
    if (!record.steps.open_site?.passed) throw new Error("open_site failed");
    await step(page, record, "open_correct_exercise", async () => {
      const found = await chooseLibraryExercise(page, target, record.library_probe || (record.library_probe = {}));
      record.url = page.url();
      return found;
    });
    if (!record.steps.open_correct_exercise?.passed) throw new Error("open_correct_exercise failed");
    await step(page, record, "verify_workbench_identity", () => verifyWorkbenchIdentity(page, target, record));
    if (!record.steps.verify_workbench_identity?.passed) throw new Error("Workbench identity verification failed");
    if (options.openOnly) {
      await screenshot(page, record, "workbench-opened");
      record.open_only = true;
      return;
    }
    await step(page, record, "inspect_statement_samples_and_leakage", () => inspectWorkbench(page, record));
    await step(page, record, "inspect_starter_layout_and_monaco", () => inspectMonaco(page));
    if (target.language === "Java") await step(page, record, "inspect_java_files_and_scroll", () => inspectJavaFiles(page, record));
    if (options.implementationMap) await step(page, record, "apply_audited_implementation", () => applyAuditedImplementation(page, target, record));
    await step(page, record, "run_current_code", () => runInteractive(page, target, record));
    await step(page, record, "run_single_and_all_public_tests", () => runPublicTest(page, record));
    await step(page, record, "submit_current_code", () => runSubmit(page, record));
    await step(page, record, "switch_topic_without_residue", () => cleanTopicSwitch(page, record));
  } catch (error) {
    record.top_level_error = String(error?.message || error).slice(0, 800);
    record.failure_category = record.steps.open_correct_exercise && !record.steps.open_correct_exercise.passed
      ? "workbench_probe_failed"
      : "workbench_acceptance_failed";
  } finally {
    record.url = page ? String(page.url()) : record.url;
    record.final_status = record.failure_steps.length || record.top_level_error ? "failed" : "passed";
    record.finished_at = now();
    if (context && options.trace) {
      ensureDir(DEFAULT_TRACE_DIR);
      const traceFile = path.join(DEFAULT_TRACE_DIR, `cli-${record.exercise_id}.zip`);
      await context.tracing.stop({ path: traceFile }).catch(() => {});
      if (fs.existsSync(traceFile)) record.traces.push(path.relative(PROJECT_ROOT, traceFile).replaceAll("\\", "/"));
    }
    writeReport(activeReport);
    if (record.failure_category === "workbench_probe_failed") {
      console.error(`WORKBENCH_PROBE_FAILED: exercise ${record.exercise_id} was not opened.`);
    }
    if (context) await context.close().catch(() => {});
  }
}

if (options.authCheckOnly) {
  const authOk = await runAuthCheck();
  process.exitCode = authOk ? 0 : 20;
} else {
  const targets = buildTargets();
  if (!targets.length) {
    console.error("No target exercises selected. Use --exercise, --group, or --language.");
    process.exitCode = 2;
  }
  activeReport = loadOrCreateReport(targets);
  writeReport(activeReport);

  if (targets.length) {
    let browser;
    try {
      if (!options.storageState || !fs.existsSync(options.storageState)) {
        activeReport.status = "auth_state_missing";
        activeReport.auth_error = `AUTH_STATE_MISSING: ${path.relative(PROJECT_ROOT, options.storageState || DEFAULT_AUTH_STATE).replaceAll("\\", "/")}`;
        writeReport(activeReport);
        console.error(activeReport.auth_error);
        process.exitCode = 20;
      } else if (!(await runAuthCheck())) {
        activeReport.status = "auth_state_expired";
        activeReport.auth_error = "AUTH_STATE_EXPIRED_OR_LOGIN_REDIRECT: see programming-workbench-auth-bootstrap.json";
        writeReport(activeReport);
        console.error(activeReport.auth_error);
        process.exitCode = 20;
      } else {
        browser = await chromium.launch({ headless: !options.headed });
        for (const target of targets) {
          // An open-only probe proves navigation/identity only. It must be
          // re-run for the full acceptance chain even though the record has
          // no failed steps and therefore carries final_status=passed.
          const existingRecord = activeReport.records[target.id];
          const fullAcceptancePassed = existingRecord?.final_status === "passed" && existingRecord?.open_only !== true;
          if (options.resume && fullAcceptancePassed) continue;
          await runTarget(browser, target);
        }
        activeReport.status = activeReport.totals.incomplete ? "incomplete" : activeReport.totals.failed ? "failed" : "passed";
        const selectedFailed = targets.filter((target) => activeReport.records[target.id]?.final_status === "failed").length;
        if (selectedFailed) process.exitCode = 30;
      }
    } catch (error) {
      activeReport.status = "runner_error";
      activeReport.runner_error = String(error?.message || error).slice(0, 800);
      writeReport(activeReport);
    } finally {
      if (browser) await browser.close().catch(() => {});
      writeReport(activeReport);
    }
  }
}
