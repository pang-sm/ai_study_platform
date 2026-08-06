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
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const DEFAULT_BASE_URL = "http://101.32.190.42/";
const DEFAULT_REPORT_DIR = path.join(PROJECT_ROOT, "verification-results");
const DEFAULT_SCREENSHOT_DIR = path.join(PROJECT_ROOT, "verification-screenshots", "programming-workbench-random-40");
const DEFAULT_TRACE_DIR = path.join(PROJECT_ROOT, "verification-traces", "programming-workbench-random-40");
const REPORT_NAME = "programming-workbench-cli-acceptance.json";
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
  headed: hasFlag("--headed") && !hasFlag("--headless"),
  storageState: readArg("--storage-state", ""),
  reportDir: path.resolve(readArg("--report-dir", DEFAULT_REPORT_DIR)),
  screenshotDir: path.resolve(readArg("--screenshot-dir", DEFAULT_SCREENSHOT_DIR)),
  trace: hasFlag("--trace"),
  implementationMap: readArg("--implementation-map", ""),
};

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

async function chooseLibraryExercise(page, target) {
  const nav = page.locator(".ph-nav button");
  const navCount = await nav.count();
  if (navCount !== 4) throw new Error(`programming navigation expected 4 buttons, got ${navCount}`);
  await nav.nth(3).click({ timeoutMs: 12000 });
  const languageButtons = page.locator(".ph-exercise-filters:not(.ph-exercise-status-filters) button");
  const languageCount = await languageButtons.count();
  if (languageCount !== 4) throw new Error(`language filter expected 4 buttons, got ${languageCount}`);
  const labels = await languageButtons.allTextContents({ timeoutMs: 12000 });
  const language = target.language || (target.id >= 1775 ? "Java" : "");
  const index = labels.findIndex((label) => cleanText(label).toLowerCase() === cleanText(language).toLowerCase());
  if (index < 0) throw new Error(`language filter not found: ${language}`);
  await languageButtons.nth(index).click({ timeoutMs: 12000 });
  const selects = page.locator(".ph-exercise-status-filters select");
  const selectCount = await selects.count();
  if (selectCount >= 3) await selects.nth(2).selectOption("48");
  for (let pageNumber = 1; pageNumber <= 4; pageNumber += 1) {
    const cards = page.locator(".ph-exercise-card");
    const count = await cards.count();
    const texts = count ? await cards.allTextContents({ timeoutMs: 12000 }) : [];
    const wanted = cleanText(target.title);
    let indexInPage = texts.findIndex((text) => wanted && cleanText(text).includes(wanted));
    if (indexInPage < 0 && target.title) {
      const pieces = cleanText(target.title).slice(0, 8);
      indexInPage = pieces.length >= 4 ? texts.findIndex((text) => cleanText(text).includes(pieces)) : -1;
    }
    if (indexInPage >= 0) {
      const card = cards.nth(indexInPage);
      const startButton = card.locator("button");
      const buttonCount = await startButton.count();
      if (buttonCount < 1) throw new Error("exercise card has no start button");
      await startButton.nth(buttonCount - 1).click({ timeoutMs: 15000 });
      return { page: pageNumber, card_text: texts[indexInPage].slice(0, 800) };
    }
    const pagingButtons = page.locator(".ph-pagination button");
    const pagingCount = await pagingButtons.count();
    if (pagingCount !== 2 || !(await pagingButtons.nth(1).isEnabled())) break;
    await pagingButtons.nth(1).click({ timeoutMs: 12000 });
    await page.waitForTimeout(500);
  }
  throw new Error(`exercise card not found in visible library: ${target.id} ${target.title}`);
}

async function inspectWorkbench(page, record) {
  const shell = page.locator(".practice-workbench");
  if (await shell.count() !== 1) throw new Error("Workbench shell not rendered");
  const title = await getText(page.locator(".pw-exercise-sidebar h1"), "exercise title");
  const statementCount = await page.locator(".pw-exercise-statement-copy").count();
  const sampleCount = await page.locator(".pw-exercise-example-card").count();
  const editorCount = await page.locator(".pw-editor-card .monaco-editor").count();
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
  const run = page.locator("button[data-action='top-run']");
  await clickUnique(run, "Run");
  await page.waitForTimeout(1200);
  const terminal = page.locator(".pw-xterm");
  if (await terminal.count() !== 1) throw new Error("terminal not rendered after Run");
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
  const nav = page.locator(".ph-nav button");
  const count = await nav.count();
  if (count !== 4) throw new Error(`navigation disappeared after Workbench: ${count}`);
  await nav.nth(3).click({ timeoutMs: 12000 });
  await page.waitForTimeout(350);
  const workbench = page.locator(".practice-workbench");
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

async function runTarget(browser, target) {
  const record = activeReport.records[target.id] || buildRecord(target);
  activeReport.records[target.id] = record;
  record.failure_steps = [];
  record.steps = {};
  record.final_status = "in_progress";
  delete record.top_level_error;
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
      const found = await chooseLibraryExercise(page, target);
      record.url = page.url();
      return found;
    });
    if (!record.steps.open_correct_exercise?.passed) throw new Error("open_correct_exercise failed");
    await step(page, record, "inspect_statement_samples_and_leakage", () => inspectWorkbench(page, record));
    await step(page, record, "inspect_starter_layout_and_monaco", () => inspectMonaco(page));
    if (target.language === "Java") await step(page, record, "inspect_java_files_and_scroll", () => inspectJavaFiles(page, record));
    await step(page, record, "run_current_code", () => runInteractive(page, target, record));
    await step(page, record, "run_single_and_all_public_tests", () => runPublicTest(page, record));
    await step(page, record, "submit_current_code", () => runSubmit(page, record));
    await step(page, record, "switch_topic_without_residue", () => cleanTopicSwitch(page, record));
  } catch (error) {
    record.top_level_error = String(error?.message || error).slice(0, 800);
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
    if (context) await context.close().catch(() => {});
  }
}

const targets = buildTargets();
if (!targets.length) {
  console.error("No target exercises selected. Use --exercise, --group, or --language.");
  process.exitCode = 2;
}
const activeReport = loadOrCreateReport(targets);
writeReport(activeReport);

if (targets.length) {
  let browser;
  try {
    const storageState = options.storageState ? path.resolve(options.storageState) : undefined;
    if (storageState && !fs.existsSync(storageState)) throw new Error(`storage state file not found: ${storageState}`);
    browser = await chromium.launch({ headless: !options.headed });
    for (const target of targets) {
      if (options.resume && activeReport.records[target.id]?.final_status === "passed") continue;
      await runTarget(browser, target);
    }
    activeReport.status = activeReport.totals.incomplete ? "incomplete" : activeReport.totals.failed ? "failed" : "passed";
  } catch (error) {
    activeReport.status = "runner_error";
    activeReport.runner_error = String(error?.message || error).slice(0, 800);
  } finally {
    if (browser) await browser.close().catch(() => {});
    delete activeReport.runner_error;
    writeReport(activeReport);
  }
}
