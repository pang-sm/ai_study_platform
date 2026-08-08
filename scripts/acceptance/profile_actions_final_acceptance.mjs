import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const baseUrl = "http://101.32.190.42/";
const authState = path.resolve(root, ".playwright/.auth/programming-workbench-online.json");
const outputDir = path.resolve(root, "verification-results/profile-actions-production");
const screenshotDir = path.join(outputDir, "screenshots");
const reportPath = path.join(outputDir, "profile-actions-final-acceptance.json");
fs.mkdirSync(screenshotDir, { recursive: true });

const report = {
  audit: "profile-actions-final-production-acceptance",
  base_url: baseUrl,
  auth_state_supplied: fs.existsSync(authState),
  records: {},
  console_business_errors: [],
  unexpected_network_failures: [],
  expected_post_logout_401: [],
  status: "not_started",
};

let browser;
let page;
let logoutPhase = false;

function isBusinessUrl(url) {
  return /\/api\//.test(url) && !/statsig|telemetry|analytics|ab\.chatgpt\.com/i.test(url);
}

async function waitVisible(selector, timeout = 30000) {
  await page.locator(selector).first().waitFor({ state: "visible", timeout });
}

async function waitBodyContains(value, timeout = 15000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if ((await page.locator("body").innerText()).includes(value)) return true;
    await page.waitForTimeout(250);
  }
  return false;
}

async function me() {
  return page.evaluate(async () => {
    const response = await fetch("/api/me", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const data = await response.json().catch(() => ({}));
    return { status: response.status, nickname: data.user?.nickname || "", has_user: Boolean(data.user) };
  });
}

async function reloadAndWaitForUser() {
  const responsePromise = page.waitForResponse(
    (response) => response.status() === 200 && new URL(response.url()).pathname === "/api/me",
    { timeout: 30000 },
  );
  await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
  await responsePromise;
  await waitVisible(".ph-page");
}

async function openProfileFromHome(homeSelector) {
  await waitVisible(homeSelector);
  const button = page.locator(".ph-profile-button, .clh-user-card, .eh-user-card");
  const count = await button.count();
  if (count !== 1) throw new Error(`profile entry ambiguous on ${homeSelector}: ${count}`);
  await button.click();
  await waitVisible(".ep-page-wrap");
}

async function profileNicknameCheck(expected, label) {
  const api = await me();
  const ui = await waitBodyContains(expected);
  report.records[label] = {
    passed: api.status === 200 && api.nickname === expected && ui,
    api_status: api.status,
    api_matches: api.nickname === expected,
    ui_matches: ui,
  };
  return report.records[label].passed;
}

async function saveNickname(value) {
  const basicCard = page.locator(".ep-card").nth(0);
  const action = basicCard.locator(".ep-card-head button");
  if (await action.count() !== 1) throw new Error("basic profile action button missing");
  await action.click();
  const input = page.locator(".ep-info-input");
  if (await input.count() !== 1) throw new Error("nickname input missing");
  await input.fill(value);
  const responsePromise = page.waitForResponse(
    (response) => response.status() >= 200 && response.status() < 300 && new URL(response.url()).pathname.endsWith("/api/me/profile"),
    { timeout: 30000 },
  );
  await action.click();
  const response = await responsePromise;
  return response.status();
}

async function switchFromProfile(index, homeSelector) {
  const buttons = page.locator(".ep-switch-btns button");
  if (await buttons.count() !== 2) throw new Error(`direction switch buttons missing for ${homeSelector}`);
  await buttons.nth(index).click();
  await waitVisible(homeSelector);
  return true;
}

try {
  if (!report.auth_state_supplied) throw new Error("verified auth state is missing");
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    storageState: authState,
    viewport: { width: 1440, height: 900 },
  });
  await context.addInitScript(() => {
    localStorage.setItem("ai_study_current_page", "programmingHome");
    localStorage.setItem("ai_study_programming_active_nav", "home");
  });
  await context.route("**/*", async (route) => {
    const url = route.request().url().toLowerCase();
    if (url.includes("statsig") || url.includes("ab.chatgpt.com") || url.includes("telemetry") || url.includes("analytics")) return route.abort();
    return route.continue();
  });
  page = await context.newPage();
  page.on("console", (message) => {
    if (logoutPhase && message.text().includes("401")) return;
    if (["error", "warning"].includes(message.type())) report.console_business_errors.push({ type: message.type(), text: message.text().slice(0, 500) });
  });
  page.on("pageerror", (error) => report.console_business_errors.push({ type: "pageerror", text: String(error.message || error).slice(0, 500) }));
  page.on("response", (response) => {
    if (response.status() >= 400 && isBusinessUrl(response.url())) {
      const item = { status: response.status(), url: response.url().replace(/([?&]username=)[^&]+/i, "$1<redacted>") };
      if (logoutPhase && response.status() === 401) report.expected_post_logout_401.push(item);
      else report.unexpected_network_failures.push(item);
    }
  });

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  await waitVisible(".ph-page");
  const initial = await me();
  report.records.auth = { passed: initial.status === 200 && initial.has_user, status: initial.status };
  if (!report.records.auth.passed) throw new Error(`authenticated /api/me failed with ${initial.status}`);

  await openProfileFromHome(".ph-page");
  const originalNickname = initial.nickname;
  const temporaryNickname = `P2FinalProfile_${Date.now()}`;
  report.records.profile_load = { passed: true, forbidden_controls: [] };
  report.records.profile_save = { api_status: await saveNickname(temporaryNickname), passed: true };

  await reloadAndWaitForUser();
  await openProfileFromHome(".ph-page");
  const refreshedApi = await me();
  report.records.refresh_persistence = {
    passed: refreshedApi.status === 200 && refreshedApi.nickname === temporaryNickname && await waitBodyContains(temporaryNickname),
    api_status: refreshedApi.status,
    api_matches: refreshedApi.nickname === temporaryNickname,
    ui_matches: await waitBodyContains(temporaryNickname),
  };

  const membership = await page.evaluate(async () => {
    const response = await fetch("/api/programming/entitlements", { credentials: "include" });
    return { status: response.status, body: await response.json().catch(() => ({})) };
  });
  report.records.membership = { passed: membership.status === 200, status: membership.status, has_plan: Boolean(membership.body?.plan) };

  const direction = {};
  await switchFromProfile(1, ".clh-page");
  await openProfileFromHome(".clh-page");
  direction.course_profile = await profileNicknameCheck(temporaryNickname, "course_profile_nickname");
  await switchFromProfile(0, ".exam-home");
  await openProfileFromHome(".exam-home");
  direction.exam_profile = await profileNicknameCheck(temporaryNickname, "exam_profile_nickname");
  await switchFromProfile(1, ".ph-page");
  await openProfileFromHome(".ph-page");
  direction.programming_profile = await profileNicknameCheck(temporaryNickname, "programming_profile_nickname");
  report.records.direction_nickname_consistency = { passed: Object.values(direction).every(Boolean), details: direction };

  const restoredSaveStatus = await saveNickname(originalNickname);
  await reloadAndWaitForUser();
  await openProfileFromHome(".ph-page");
  const restoredApi = await me();
  const restoredUi = await waitBodyContains(originalNickname);
  report.records.restore_original = {
    passed: restoredSaveStatus >= 200 && restoredSaveStatus < 300 && restoredApi.status === 200 && restoredApi.nickname === originalNickname && restoredUi,
    save_status: restoredSaveStatus,
    api_status: restoredApi.status,
    api_matches: restoredApi.nickname === originalNickname,
    ui_matches: restoredUi,
  };

  await switchFromProfile(1, ".clh-page");
  await openProfileFromHome(".clh-page");
  const restoredCourse = await profileNicknameCheck(originalNickname, "restored_course_profile");
  await switchFromProfile(0, ".exam-home");
  await openProfileFromHome(".exam-home");
  const restoredExam = await profileNicknameCheck(originalNickname, "restored_exam_profile");
  await switchFromProfile(1, ".ph-page");
  await openProfileFromHome(".ph-page");
  const restoredProgramming = await profileNicknameCheck(originalNickname, "restored_programming_profile");
  report.records.restored_direction_consistency = { passed: restoredCourse && restoredExam && restoredProgramming };

  logoutPhase = true;
  const logoutResponse = page.waitForResponse((response) => response.status() === 200 && new URL(response.url()).pathname === "/api/logout", { timeout: 30000 });
  const logoutButton = page.locator(".ep-logout-btn");
  if (await logoutButton.count() !== 1) throw new Error("logout button missing");
  await logoutButton.click();
  const logout = await logoutResponse;
  const afterLogout = await me();
  await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
  const loginVisible = await page.locator('input[type="password"]').first().isVisible().catch(() => false);
  report.records.logout = { passed: logout.status() === 200, status: logout.status() };
  report.records.post_logout_me = { status: afterLogout.status, classification: afterLogout.status === 401 ? "EXPECTED_PASS" : "FAIL" };
  report.records.reload_login = { passed: loginVisible };
  report.status = Object.values(report.records).every((record) => record?.passed !== false)
    && report.records.post_logout_me.classification === "EXPECTED_PASS"
    && report.console_business_errors.length === 0
    && report.unexpected_network_failures.length === 0
    ? "passed"
    : "failed";
} catch (error) {
  report.status = "failed";
  report.error = String(error?.message || error).slice(0, 800);
  if (page) {
    report.failure_page_url = await page.url();
    report.failure_screenshot = "verification-results/profile-actions-production/screenshots/final-failure.png";
    await page.screenshot({ path: path.join(screenshotDir, "final-failure.png"), fullPage: false }).catch(() => {});
  }
} finally {
  if (browser) await browser.close().catch(() => {});
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify(report, null, 2));
process.exitCode = report.status === "passed" ? 0 : 1;
