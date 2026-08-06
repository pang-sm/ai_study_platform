#!/usr/bin/env node

/**
 * Opens a clean headed Chromium context for one-time manual sign-in and saves
 * only a Playwright storageState. Sensitive values are never printed or put in
 * the verification reports.
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const DEFAULT_ORIGIN = "http://101.32.190.42";
const DEFAULT_AUTH_STATE = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const REPORT_DIR = path.join(PROJECT_ROOT, "verification-results");
const JSON_REPORT = path.join(REPORT_DIR, "programming-workbench-auth-bootstrap.json");
const MD_REPORT = path.join(REPORT_DIR, "programming-workbench-auth-bootstrap.md");
const USER_STORAGE_KEY = "ai_study_platform_user";

const argv = process.argv.slice(2);
function readArg(name, fallback = "") {
  const index = argv.indexOf(name);
  return index >= 0 && argv[index + 1] ? argv[index + 1] : fallback;
}
const baseUrl = readArg("--base-url", DEFAULT_ORIGIN).replace(/\/$/, "/");
const authStatePath = path.resolve(readArg("--auth-state", DEFAULT_AUTH_STATE));
const timeoutMs = Math.max(60_000, Number(readArg("--timeout-ms", "600000")) || 600_000);

function ensureDir(dir) { fs.mkdirSync(dir, { recursive: true }); }
function now() { return new Date().toISOString(); }
function maskIdentity(value) {
  const text = String(value || "");
  if (!text) return "";
  if (text.length <= 2) return `${text[0]}*`;
  return `${text.slice(0, 1)}${"*".repeat(Math.min(6, text.length - 2))}${text.slice(-1)}`;
}
function safeError(error) {
  return String(error?.message || error || "").replace(/(password|token|cookie|authorization|secret)=[^\s&]+/gi, "$1=<redacted>").slice(0, 600);
}

async function inspectAuth(page) {
  return page.evaluate(async (storageKey) => {
    const raw = localStorage.getItem(storageKey);
    let user = null;
    try { user = raw ? JSON.parse(raw) : null; } catch { user = null; }
    const username = typeof user?.username === "string" ? user.username : "";
    let meStatus = null;
    if (username) {
      try {
        const response = await fetch("/api/me", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username }),
        });
        meStatus = response.status;
      } catch { meStatus = "network_error"; }
    }
    const bodyText = document.body?.innerText || "";
    const navCount = document.querySelectorAll(".ph-nav button").length;
    const workbench = Boolean(document.querySelector(".practice-workbench"));
    const loginForm = Boolean(document.querySelector("input[type='password']"));
    return {
      has_user: Boolean(username),
      username,
      me_status: meStatus,
      nav_count: navCount,
      workbench,
      login_form: loginForm,
      visible_user_signal: /退出|个人中心|编程学习|我的资料/.test(bodyText),
      local_storage_keys: Object.keys(localStorage),
    };
  }, USER_STORAGE_KEY);
}

function isAuthenticated(snapshot) {
  return Boolean(snapshot?.has_user && snapshot.me_status === 200 && (snapshot.nav_count === 4 || snapshot.workbench || snapshot.visible_user_signal));
}

function writeReports(report) {
  ensureDir(REPORT_DIR);
  fs.writeFileSync(JSON_REPORT, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  const auth = report.authentication || {};
  const lines = [
    "# Workbench 登录态引导验收",
    "",
    `- 时间：${report.generated_at}`,
    `- origin：${report.origin}`,
    `- 登录态验证：${report.status}`,
    `- Cookie 数量：${auth.cookie_count ?? 0}`,
    `- localStorage key：${(auth.local_storage_keys || []).join(", ") || "无"}`,
    `- 用户标识（脱敏）：${auth.redacted_identity || "未读取到"}`,
    `- /api/me 状态：${auth.me_status ?? "未调用"}`,
    `- storageState：${report.storage_state_path}`,
    "",
    report.error ? `- 错误：${report.error}` : "- 敏感值未写入报告。",
  ];
  fs.writeFileSync(MD_REPORT, `${lines.join("\n")}\n`, "utf8");
}

const report = {
  audit: "programming-workbench-auth-bootstrap",
  generated_at: now(),
  origin: new URL(baseUrl).origin,
  storage_state_path: path.relative(PROJECT_ROOT, authStatePath).replaceAll("\\", "/"),
  status: "in_progress",
  authentication: {},
  policy: {
    headed_chromium: true,
    independent_context: true,
    sensitive_values_written: false,
    cookies_written_to_report: false,
  },
};

let browser;
try {
  ensureDir(path.dirname(authStatePath));
  browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await context.route("**/*", async (route) => {
    const host = new URL(route.request().url()).hostname.toLowerCase();
    if (host.includes("statsig") || host === "ab.chatgpt.com" || host.includes("analytics") || host.includes("telemetry")) return route.abort();
    return route.continue();
  });
  const page = await context.newPage();
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 45_000 });
  console.log(`LOGIN_BOOTSTRAP_OPENED origin=${new URL(baseUrl).origin}`);
  console.log("请在新打开的独立 Chromium 窗口中手动完成登录；脚本会自动检测成功，不会记录密码、Cookie 或 token。");

  const deadline = Date.now() + timeoutMs;
  let snapshot = await inspectAuth(page);
  while (!isAuthenticated(snapshot) && Date.now() < deadline) {
    await page.waitForTimeout(1000);
    snapshot = await inspectAuth(page);
  }
  if (!isAuthenticated(snapshot)) throw new Error("manual login was not detected before timeout");

  await context.storageState({ path: authStatePath });
  const state = JSON.parse(fs.readFileSync(authStatePath, "utf8"));
  const stateOrigins = (state.origins || []).map((item) => item.origin);
  const cookies = Array.isArray(state.cookies) ? state.cookies : [];
  if (!stateOrigins.includes(new URL(baseUrl).origin)) throw new Error("storageState does not contain the formal site origin");
  report.authentication = {
    cookie_count: cookies.length,
    local_storage_keys: snapshot.local_storage_keys,
    redacted_identity: maskIdentity(snapshot.username),
    me_status: snapshot.me_status,
    detected_route: snapshot.workbench ? "workbench" : snapshot.nav_count === 4 ? "programming_home" : "authenticated_page",
    origin_in_storage_state: true,
  };
  report.status = "passed";
  writeReports(report);
  console.log(`AUTH_STORAGE_SAVED path=${report.storage_state_path}`);
  console.log(`AUTH_VERIFY origin=${report.origin} cookies=${cookies.length} localStorageKeys=${snapshot.local_storage_keys.join(",")} user=${report.authentication.redacted_identity} result=passed`);
  await context.close();
} catch (error) {
  report.status = "failed";
  report.error = safeError(error);
  writeReports(report);
  console.error(`AUTH_BOOTSTRAP_FAILED ${report.error}`);
  process.exitCode = 20;
} finally {
  if (browser) await browser.close().catch(() => {});
}
