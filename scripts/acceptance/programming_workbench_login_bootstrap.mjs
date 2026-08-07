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
const timeoutMs = Math.min(900_000, Math.max(60_000, Number(readArg("--timeout-ms", "900000")) || 900_000));
const autoMode = argv.includes("--auto");
const headed = argv.includes("--headed") || !autoMode;
const screenshotDir = path.join(PROJECT_ROOT, "verification-screenshots", "programming-workbench-auth");

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

function parseSetCookieMetadata(headerValue) {
  const header = String(headerValue || "");
  const sessionPart = header.split(/,(?=\s*ai_session=)/i).find((part) => /^\s*ai_session=/i.test(part));
  const attributes = String(sessionPart || "").split(";").slice(1).map((part) => part.trim());
  const valueFor = (name) => {
    const item = attributes.find((part) => part.toLowerCase().startsWith(`${name.toLowerCase()}=`));
    return item ? item.slice(item.indexOf("=") + 1) : "";
  };
  return {
    present: Boolean(sessionPart),
    path: valueFor("Path") || null,
    domain: valueFor("Domain") || null,
    same_site: valueFor("SameSite") || null,
    secure: attributes.some((part) => part.toLowerCase() === "secure"),
    http_only: attributes.some((part) => part.toLowerCase() === "httponly"),
  };
}

async function requestCurrentUser(page) {
  return page.evaluate(async () => {
    try {
      const response = await fetch("/api/me", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const data = await response.json().catch(() => ({}));
      return { status: response.status, username: data?.user?.username || "" };
    } catch {
      return { status: "network_error", username: "" };
    }
  });
}

async function autoLogin(page, context) {
  const acceptanceUsername = String(process.env.ACCEPTANCE_USERNAME || "").trim();
  const acceptancePassword = String(process.env.ACCEPTANCE_PASSWORD || "");
  if (!acceptanceUsername || !acceptancePassword) {
    throw new Error("auto bootstrap requires ACCEPTANCE_USERNAME and ACCEPTANCE_PASSWORD");
  }
  const usernameInput = page.locator('input[aria-label="账号"]');
  const passwordInput = page.locator('input[type="password"]');
  const submitButton = page.locator("button.auth-submit");
  if (await usernameInput.count() !== 1 || await passwordInput.count() !== 1 || await submitButton.count() !== 1) {
    throw new Error("login form controls were not found");
  }
  await usernameInput.waitFor({ state: "visible", timeout: 30_000 });
  await passwordInput.waitFor({ state: "visible", timeout: 30_000 });
  const loginResponsePromise = page.waitForResponse((response) => {
    try {
      return response.request().method() === "POST" && new URL(response.url()).pathname.endsWith("/login");
    } catch {
      return false;
    }
  }, { timeout: 30_000 });
  await usernameInput.fill(acceptanceUsername);
  await passwordInput.fill(acceptancePassword);
  await submitButton.click();
  const loginResponse = await loginResponsePromise;
  const headers = await loginResponse.headers();
  const setCookieMetadata = parseSetCookieMetadata(headers["set-cookie"] || headers["Set-Cookie"] || "");
  const loginMeta = { login_status: loginResponse.status(), set_cookie: setCookieMetadata };
  if (loginResponse.status() < 200 || loginResponse.status() >= 300) {
    const error = new Error(`login response status=${loginResponse.status()}`);
    error.authMeta = loginMeta;
    throw error;
  }
  const cookies = await context.cookies(new URL(baseUrl).origin);
  const sessionCookie = cookies.find((cookie) => cookie.name === "ai_session");
  const cookieMeta = {
    ...loginMeta,
    ai_session_present: Boolean(sessionCookie),
    cookie_count: cookies.length,
    cookie: sessionCookie ? {
      domain: sessionCookie.domain,
      path: sessionCookie.path,
      same_site: sessionCookie.sameSite || null,
      secure: sessionCookie.secure,
      http_only: sessionCookie.httpOnly,
    } : null,
  };
  if (!sessionCookie) {
    const error = new Error("login response succeeded but ai_session was not stored in browser context");
    error.authMeta = cookieMeta;
    throw error;
  }
  const me = await requestCurrentUser(page);
  const identityMatch = me.status === 200 && me.username === acceptanceUsername;
  if (me.status !== 200 || !identityMatch) {
    const error = new Error(`authenticated /api/me check failed status=${me.status}`);
    error.authMeta = { ...cookieMeta, me_status: me.status, identity_match: identityMatch, redacted_identity: maskIdentity(me.username) };
    throw error;
  }
  return {
    ...cookieMeta,
    me_status: me.status,
    identity_match: identityMatch,
    redacted_identity: maskIdentity(me.username),
  };
}

async function inspectAuth(page) {
  return page.evaluate(async (storageKey) => {
    const raw = localStorage.getItem(storageKey);
    let user = null;
    try { user = raw ? JSON.parse(raw) : null; } catch { user = null; }
    const storageUsername = typeof user?.username === "string" ? user.username : "";
    let meStatus = null;
    let serverUsername = "";
    try {
      const response = await fetch("/api/me", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const data = await response.json().catch(() => ({}));
      meStatus = response.status;
      serverUsername = typeof data?.user?.username === "string" ? data.user.username : "";
    } catch { meStatus = "network_error"; }
    const bodyText = document.body?.innerText || "";
    const navCount = document.querySelectorAll(".ph-nav button").length;
    const workbench = Boolean(document.querySelector(".practice-workbench"));
    const loginForm = Boolean(document.querySelector("input[type='password']"));
    return {
      has_user: Boolean(serverUsername || storageUsername),
      username: serverUsername || storageUsername,
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
  return snapshot?.me_status === 200;
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
  screenshots: [],
  policy: {
    headed_chromium: true,
    independent_context: true,
    sensitive_values_written: false,
    cookies_written_to_report: false,
  },
};

let browser;
let primaryContext;
let primaryPage;
let probeContext;
let probePage;
try {
  ensureDir(path.dirname(authStatePath));
  if (autoMode && (!process.env.ACCEPTANCE_USERNAME || !process.env.ACCEPTANCE_PASSWORD)) {
    throw new Error("auto bootstrap requires ACCEPTANCE_USERNAME and ACCEPTANCE_PASSWORD");
  }
  browser = await chromium.launch({ headless: !headed });
  primaryContext = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await primaryContext.route("**/*", async (route) => {
    const host = new URL(route.request().url()).hostname.toLowerCase();
    if (host.includes("statsig") || host === "ab.chatgpt.com" || host.includes("analytics") || host.includes("telemetry")) return route.abort();
    return route.continue();
  });
  primaryPage = await primaryContext.newPage();
  await primaryPage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 45_000 });
  console.log(`LOGIN_BOOTSTRAP_OPENED origin=${new URL(baseUrl).origin} mode=${autoMode ? "auto" : "manual"}`);
  if (!autoMode) console.log("Complete sign-in in the visible Chromium window. Passwords, cookies, and tokens are not logged.");

  let autoLoginResult = null;
  let snapshot;
  if (autoMode) {
    autoLoginResult = await autoLogin(primaryPage, primaryContext);
    snapshot = await inspectAuth(primaryPage);
  } else {
    const deadline = Date.now() + timeoutMs;
    snapshot = await inspectAuth(primaryPage);
    while (!isAuthenticated(snapshot) && Date.now() < deadline) {
      await primaryPage.waitForTimeout(1000);
      snapshot = await inspectAuth(primaryPage);
    }
    if (!isAuthenticated(snapshot)) throw new Error("manual login was not detected before timeout");
  }

  await primaryContext.storageState({ path: authStatePath });
  const state = JSON.parse(fs.readFileSync(authStatePath, "utf8"));
  const stateOrigins = (state.origins || []).map((item) => item.origin);
  const cookies = Array.isArray(state.cookies) ? state.cookies : [];
  if (!stateOrigins.includes(new URL(baseUrl).origin)) throw new Error("storageState does not contain the formal site origin");
  report.authentication = {
    cookie_count: cookies.length,
    ai_session_present: Boolean(cookies.find((cookie) => cookie.name === "ai_session")),
    ...(autoLoginResult || {}),
    local_storage_keys: snapshot.local_storage_keys,
    redacted_identity: maskIdentity(snapshot.username),
    me_status: snapshot.me_status,
    detected_route: snapshot.workbench ? "workbench" : snapshot.nav_count === 4 ? "programming_home" : "authenticated_page",
    origin_in_storage_state: true,
  };
  await primaryContext.close();
  primaryContext = null;

  // Validate persistence in a brand-new context, not the context that performed
  // the manual login. This catches wrong origins and session-only state.
  probeContext = await browser.newContext({ storageState: authStatePath, viewport: { width: 1366, height: 768 } });
  await probeContext.route("**/*", async (route) => {
    const host = new URL(route.request().url()).hostname.toLowerCase();
    if (host.includes("statsig") || host === "ab.chatgpt.com" || host.includes("analytics") || host.includes("telemetry")) return route.abort();
    return route.continue();
  });
  probePage = await probeContext.newPage();
  await probePage.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 45_000 });
  const probeSnapshot = await inspectAuth(probePage);
  const probeMe = await requestCurrentUser(probePage);
  if (!isAuthenticated(probeSnapshot) || probeSnapshot.login_form || probeMe.status !== 200) throw new Error(`fresh context auth probe failed: /api/me=${probeMe.status ?? "missing"}`);
  report.authentication.fresh_context_probe = {
    passed: true,
    me_status: probeMe.status,
    origin: new URL(baseUrl).origin,
    local_storage_keys: probeSnapshot.local_storage_keys,
  };
  report.status = "passed";
  writeReports(report);
  console.log(`AUTH_STORAGE_SAVED path=${report.storage_state_path}`);
  console.log(`AUTH_VERIFY origin=${report.origin} cookies=${cookies.length} ai_session_present=${report.authentication.ai_session_present} me_status=${report.authentication.me_status} reload_me_status=${report.authentication.fresh_context_probe.me_status} identity_match=${report.authentication.identity_match ?? true} result=passed`);
  await probeContext.close();
  probeContext = null;
} catch (error) {
  const screenshotPath = path.join(screenshotDir, "login-bootstrap-failure.png");
  try {
    ensureDir(screenshotDir);
    const pageForScreenshot = probePage || primaryPage;
    if (pageForScreenshot) {
      await pageForScreenshot.screenshot({ path: screenshotPath, fullPage: false });
      report.screenshots.push(path.relative(PROJECT_ROOT, screenshotPath).replaceAll("\\", "/"));
    }
  } catch { /* preserve the primary error */ }
  if (error?.authMeta) report.authentication = { ...report.authentication, ...error.authMeta };
  report.status = "failed";
  report.error = safeError(error);
  writeReports(report);
  console.error(`AUTH_BOOTSTRAP_FAILED ${report.error}`);
  process.exitCode = 20;
} finally {
  if (probeContext) await probeContext.close().catch(() => {});
  if (primaryContext) await primaryContext.close().catch(() => {});
  if (browser) await browser.close().catch(() => {});
}
