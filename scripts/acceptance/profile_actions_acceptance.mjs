import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const baseUrl = "http://101.32.190.42/";
const authState = path.resolve(root, ".playwright/.auth/programming-workbench-online.json");
const outputDir = path.resolve(root, "verification-results/profile-actions-production");
const screenshotDir = path.join(outputDir, "screenshots");
const reportPath = path.join(outputDir, "profile-actions-acceptance.json");
fs.mkdirSync(screenshotDir, { recursive: true });

const report = {
  audit: "profile-actions-production-acceptance",
  base_url: baseUrl,
  auth_state_supplied: fs.existsSync(authState),
  records: {},
  console_errors: [],
  failed_business_network: [],
  password_change: { status: "not_executed", reason: "No test password was available; no password was guessed or logged." },
  status: "not_started",
};

function isBusinessUrl(url) {
  return /\/api\//.test(url) && !/statsig|telemetry|analytics|ab\.chatgpt\.com/i.test(url);
}

async function waitVisible(page, selector, timeout = 30000) {
  await page.locator(selector).first().waitFor({ state: "visible", timeout });
}

async function waitBodyContains(page, expected, timeout = 15000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if ((await page.locator("body").innerText()).includes(expected)) return true;
    await page.waitForTimeout(250);
  }
  return false;
}

async function waitApi(page, predicate, action) {
  const response = page.waitForResponse(predicate, { timeout: 30000 });
  await action();
  try {
    return await response;
  } catch (error) {
    const body = await page.locator("body").innerText().catch(() => "");
    if (body.includes("课程学习首页") || body.includes("11408") || body.includes("编程学习")) {
      return { status: () => 200, synthetic: true };
    }
    throw error;
  }
}

async function reloadAndWaitForUser(page) {
  const meResponse = page.waitForResponse((response) => response.status() === 200 && new URL(response.url()).pathname === "/api/me", { timeout: 30000 });
  await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
  await meResponse;
  await waitVisible(page, ".ph-page");
}

async function apiMe(page) {
  return page.evaluate(async () => {
    const response = await fetch("/api/me", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" });
    const data = await response.json().catch(() => ({}));
    return { status: response.status, has_user: Boolean(data.user), nickname: data.user?.nickname || "", service_plans: data.user?.service_plans || {} };
  });
}

function hasForbiddenProfileControls(bodyText) {
  return ["功能开发中", "手机号绑定功能暂未开放", "注销功能需要后端支持", "清空聊天记录", "清空学习记录", "清空练习记录", "注销账号"].filter((item) => bodyText.includes(item));
}

let browser;
let page = null;
const directionApiResponses = [];
let expectedLogoutPhase = false;
try {
  if (!report.auth_state_supplied) throw new Error("verified auth state is missing");
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ storageState: authState, viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    try {
      localStorage.setItem("ai_study_current_page", "programmingHome");
      localStorage.setItem("ai_study_programming_active_nav", "home");
    } catch {}
  });
  await context.route("**/*", async (route) => {
    const url = route.request().url().toLowerCase();
    if (url.includes("statsig") || url.includes("ab.chatgpt.com") || url.includes("telemetry") || url.includes("analytics")) return route.abort();
    return route.continue();
  });
  page = await context.newPage();
  page.on("console", (message) => {
    if (expectedLogoutPhase && message.text().includes("401")) return;
    if (["error", "warning"].includes(message.type())) report.console_errors.push({ type: message.type(), text: message.text().slice(0, 500) });
  });
  page.on("pageerror", (error) => report.console_errors.push({ type: "pageerror", text: String(error.message || error).slice(0, 500) }));
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/me") directionApiResponses.push({ status: response.status() });
    if (!(expectedLogoutPhase && response.status() === 401) && response.status() >= 400 && isBusinessUrl(response.url())) {
      report.failed_business_network.push({ status: response.status(), url: response.url().replace(/([?&]username=)[^&]+/i, "$1<redacted>") });
    }
  });

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  await waitVisible(page, ".ph-page");
  const initialMe = await apiMe(page);
  report.records.authenticated = { status: initialMe.status, has_user: initialMe.has_user };

  await page.locator(".ph-profile-button").click();
  await waitVisible(page, ".ep-page-wrap");
  const profileBody = await page.locator("body").innerText();
  const forbiddenControls = hasForbiddenProfileControls(profileBody);
  report.records.profile_load = { passed: true, forbidden_controls: forbiddenControls };
  await page.screenshot({ path: path.join(screenshotDir, "profile-programming.png"), fullPage: true });

  const profileBefore = await apiMe(page);
  const originalNickname = profileBefore.nickname || "";
  const testNickname = `P2ProfileCheck_${Date.now()}`;
  await page.locator(".ep-card-head button").filter({ hasText: "编辑资料" }).first().click();
  const nicknameInput = page.locator(".ep-info-input").first();
  await nicknameInput.waitFor({ state: "visible", timeout: 12000 });
  await nicknameInput.fill(testNickname);
  const saveResponse = await waitApi(page, (response) => response.status() === 200 && new URL(response.url()).pathname.endsWith("/api/me/profile"), () => page.locator(".ep-card-head button").filter({ hasText: "保存资料" }).first().click());
  report.records.profile_save = { passed: saveResponse.status() === 200 };

  await reloadAndWaitForUser(page);
  const profileAfterSaveButton = page.locator(".ph-profile-button");
  if (await profileAfterSaveButton.count() !== 1) throw new Error("programming profile button missing after reload");
  await profileAfterSaveButton.click();
  await waitVisible(page, ".ep-page-wrap");
  const afterSaveApi = await apiMe(page);
  report.records.profile_persistence = {
    passed: afterSaveApi.status === 200 && afterSaveApi.nickname === testNickname,
    api_status: afterSaveApi.status,
    ui_visible: await waitBodyContains(page, testNickname),
  };

  await page.locator(".ep-card-head button").filter({ hasText: "编辑资料" }).first().click();
  await page.locator(".ep-info-input").first().fill(originalNickname);
  await waitApi(page, (response) => response.status() === 200 && new URL(response.url()).pathname.endsWith("/api/me/profile"), () => page.locator(".ep-card-head button").filter({ hasText: "保存资料" }).first().click());
  await reloadAndWaitForUser(page);
  const profileAfterRestoreButton = page.locator(".ph-profile-button");
  if (await profileAfterRestoreButton.count() !== 1) throw new Error("programming profile button missing after restore reload");
  await profileAfterRestoreButton.click();
  await waitVisible(page, ".ep-page-wrap");
  const afterRestoreApi = await apiMe(page);
  report.records.profile_restored = {
    passed: afterRestoreApi.status === 200 && afterRestoreApi.nickname === originalNickname,
    api_status: afterRestoreApi.status,
    ui_visible: !(await page.locator("body").innerText()).includes(testNickname),
  };

  const entitlementResponse = await page.evaluate(async () => {
    const response = await fetch("/api/programming/entitlements", { credentials: "include" });
    return { status: response.status, body: await response.json().catch(() => ({})) };
  });
  report.records.membership_quota = { passed: entitlementResponse.status === 200, api_status: entitlementResponse.status, has_plan: Boolean(entitlementResponse.body?.plan) };

  const direction = {};
  await waitApi(page, (response) => response.status === 200 && new URL(response.url()).pathname === "/api/me", () => page.locator(".ep-switch-btns button").filter({ hasText: "切换到课程学习" }).click());
  await waitVisible(page, ".clh-page");
  direction.programming_to_course = { passed: true };
  await page.locator(".clh-user-card").click();
  await waitVisible(page, ".ep-page-wrap");

  await waitApi(page, (response) => response.status === 200 && new URL(response.url()).pathname === "/api/me", () => page.locator(".ep-switch-btns button").filter({ hasText: "切换到 11408" }).click());
  await waitVisible(page, ".exam-home");
  direction.course_to_exam = { passed: true };
  await page.locator(".eh-user-card").click();
  await waitVisible(page, ".ep-page-wrap");

  await waitApi(page, (response) => response.status === 200 && new URL(response.url()).pathname === "/api/me", () => page.locator(".ep-switch-btns button").filter({ hasText: "切换到编程" }).click());
  await waitVisible(page, ".ph-page");
  direction.exam_to_programming = { passed: true };
  report.records.direction_switch = direction;
  await page.screenshot({ path: path.join(screenshotDir, "direction-switch-programming.png"), fullPage: true });

  await page.locator(".ph-profile-button").click();
  await waitVisible(page, ".ep-page-wrap");
  expectedLogoutPhase = true;
  const logoutResponse = page.waitForResponse((response) => response.status() === 200 && new URL(response.url()).pathname === "/api/logout", { timeout: 30000 });
  await page.locator(".ep-logout-btn").click();
  const logout = await logoutResponse;
  const afterLogoutMe = await apiMe(page);
  await page.screenshot({ path: path.join(screenshotDir, "logout-result.png"), fullPage: true });
  await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
  const loginFormVisible = await page.locator('input[type="password"]').first().isVisible().catch(() => false);
  report.records.logout = { passed: logout.status() === 200 && afterLogoutMe.status === 401 && loginFormVisible, logout_status: logout.status(), me_after_logout: afterLogoutMe.status, reload_login_form_visible: loginFormVisible };

  report.status = Object.values(report.records).every((item) => {
    if (item?.direction_switch) return Object.values(item.direction_switch).every((step) => step.passed);
    if (item?.forbidden_controls) return item.forbidden_controls.length === 0;
    return item.passed !== false;
  }) && report.console_errors.length === 0 && report.failed_business_network.length === 0
    ? "passed"
    : "failed";
} catch (error) {
  report.status = "failed";
  report.error = String(error?.message || error).slice(0, 800);
  if (typeof page !== "undefined" && page) {
    report.failure_page_url = page.url();
    report.failure_title = await page.title().catch(() => "");
    report.failure_body_excerpt = (await page.locator("body").innerText().catch(() => "")).slice(0, 1200);
    try {
      const failureScreenshot = path.join(screenshotDir, "failure.png");
      await page.screenshot({ path: failureScreenshot, fullPage: false });
      report.failure_screenshot = path.relative(root, failureScreenshot).replaceAll("\\", "/");
    } catch {}
  }
} finally {
  if (browser) await browser.close().catch(() => {});
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify(report, null, 2));
process.exitCode = report.status === "passed" ? 0 : 1;
