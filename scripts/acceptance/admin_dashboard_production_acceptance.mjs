import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const baseUrl = process.env.ACCEPTANCE_BASE_URL || "https://101.32.190.42/";
const username = (process.env.ACCEPTANCE_ADMIN_USERNAME || "admin_acceptance").trim();
const password = process.env.ACCEPTANCE_ADMIN_PASSWORD || "";
const authStatePath = path.resolve(
  root,
  process.env.ACCEPTANCE_ADMIN_AUTH_STATE || ".playwright/.auth/admin-dashboard-production.json",
);
const outputDir = path.resolve(root, "verification-results/admin-dashboard-production");
const screenshotDir = path.join(outputDir, "screenshots");
const reportPath = path.join(outputDir, "acceptance-final.json");

fs.mkdirSync(path.dirname(authStatePath), { recursive: true });
fs.mkdirSync(screenshotDir, { recursive: true });

const report = {
  audit: "admin-dashboard-production-final-acceptance",
  base_url: baseUrl,
  auth_entry: "/login",
  auth_state_path: ".playwright/.auth/admin-dashboard-production.json",
  username,
  records: {},
  console_business_errors: [],
  known_third_party_noise: [],
  expected_navigation_aborts: [],
  unexpected_network_failures: [],
  screenshots: [],
  status: "not_started",
};

let browser;
let context;
let page;

function isNoiseUrl(url) {
  return /statsig|ab\.chatgpt\.com|telemetry|analytics/i.test(url);
}

function isBusinessApi(url) {
  return /\/api\//i.test(url) && !isNoiseUrl(url);
}

function formatNumber(value, digits = 0) {
  return Number(value || 0).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function screenshotPath(name) {
  const absolute = path.join(screenshotDir, name);
  report.screenshots.push(`verification-results/admin-dashboard-production/screenshots/${name}`);
  return absolute;
}

async function apiJson(pathname, options = {}) {
  return page.evaluate(async ({ pathname, options }) => {
    const response = await fetch(pathname, { credentials: "include", ...options });
    return {
      status: response.status,
      body: await response.json().catch(() => ({})),
    };
  }, { pathname, options });
}

async function getMe() {
  return apiJson("/api/me", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
}

async function waitForVisible(selector, timeout = 30000) {
  await page.locator(selector).waitFor({ state: "visible", timeout });
}

async function waitForAdminShell(timeout = 30000) {
  await waitForVisible(".admin-dashboard-shell", timeout);
  await page.locator(".admin-dashboard-stat").first().waitFor({ state: "visible", timeout }).catch(() => {});
}

function attachDiagnostics(targetPage) {
  targetPage.on("console", (message) => {
    const text = message.text();
    if (isNoiseUrl(message.location()?.url || "") || /Statsig|telemetry|analytics|ab\.chatgpt\.com/i.test(text)) {
      report.known_third_party_noise.push({ type: message.type(), text: text.slice(0, 500) });
      return;
    }
    if (["error", "warning"].includes(message.type())) {
      report.console_business_errors.push({ type: message.type(), text: text.slice(0, 500) });
    }
  });
  targetPage.on("pageerror", (error) => {
    report.console_business_errors.push({ type: "pageerror", text: String(error.message || error).slice(0, 500) });
  });
  targetPage.on("response", (response) => {
    if (response.status() >= 400 && isBusinessApi(response.url())) {
      report.unexpected_network_failures.push({ status: response.status(), url: response.url().replace(/([?&]admin_username=)[^&]+/i, "$1<redacted>") });
    }
  });
  targetPage.on("requestfailed", (request) => {
    if (isBusinessApi(request.url())) {
      if (request.failure()?.errorText === "net::ERR_ABORTED") {
        report.expected_navigation_aborts.push({ url: request.url().replace(/([?&]admin_username=)[^&]+/i, "$1<redacted>") });
        return;
      }
      report.unexpected_network_failures.push({ status: "request_failed", url: request.url().replace(/([?&]admin_username=)[^&]+/i, "$1<redacted>"), error: request.failure()?.errorText || "unknown" });
    }
  });
}

async function clickNav(label, expectedText = "") {
  const button = page.locator(".admin-dashboard-nav-item").filter({ hasText: label });
  if (await button.count() !== 1) throw new Error(`admin navigation button not unique: ${label}`);
  await button.click();
  await waitForVisible(".admin-dashboard-shell");
  if (expectedText) await page.getByText(expectedText, { exact: true }).first().waitFor({ state: "visible", timeout: 30000 });
}

async function main() {
  const savedAuthAvailable = fs.existsSync(authStatePath) && fs.statSync(authStatePath).size > 0;
  if (!password && !savedAuthAvailable) throw new Error("ACCEPTANCE_ADMIN_PASSWORD is required when no saved auth state is available");
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({
    ...(savedAuthAvailable && !password ? { storageState: authStatePath } : {}),
    viewport: { width: 1440, height: 900 },
  });
  await context.route("**/*", async (route) => {
    if (isNoiseUrl(route.request().url())) return route.abort();
    return route.continue();
  });
  page = await context.newPage();
  attachDiagnostics(page);

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  const meAfterLogin = await getMe();
  const adminRole = meAfterLogin.body?.user?.admin_role || meAfterLogin.body?.profile?.admin_role || "none";
  const isAdmin = Boolean(meAfterLogin.body?.user?.is_admin ?? meAfterLogin.body?.profile?.is_admin);
  report.records.auth = {
    passed: meAfterLogin.status === 200 && isAdmin && adminRole === "super_admin",
    login_status: savedAuthAvailable && !password ? "reused_storage_state" : "not_run",
    me_status: meAfterLogin.status,
    username_match: meAfterLogin.body?.user?.username === username || meAfterLogin.body?.profile?.username === username,
    is_admin: isAdmin,
    admin_role: adminRole,
  };
  if (!report.records.auth.passed) throw new Error(`admin authentication probe failed: me=${meAfterLogin.status}`);

  if (!(savedAuthAvailable && !password)) await context.storageState({ path: authStatePath });
  report.records.storage_state_saved = { passed: fs.statSync(authStatePath).size > 0, path: ".playwright/.auth/admin-dashboard-production.json" };

  await context.close();
  context = await browser.newContext({ storageState: authStatePath, viewport: { width: 1440, height: 900 } });
  await context.route("**/*", async (route) => {
    if (isNoiseUrl(route.request().url())) return route.abort();
    return route.continue();
  });
  page = await context.newPage();
  attachDiagnostics(page);
  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  const reloadedMe = await getMe();
  report.records.storage_state_reload = { passed: reloadedMe.status === 200 && Boolean(reloadedMe.body?.user), me_status: reloadedMe.status };
  await waitForAdminShell();

  const dashboard = await apiJson(`/api/admin/dashboard?admin_username=${encodeURIComponent(username)}`);
  const operations = await apiJson(`/api/admin/operations-dashboard?admin_username=${encodeURIComponent(username)}`);
  const usageSummary = await apiJson(`/api/admin/usage-summary?admin_username=${encodeURIComponent(username)}`);
  const usageTrend = await apiJson(`/api/admin/usage-trend?admin_username=${encodeURIComponent(username)}&days=7`);
  const permissions = await apiJson(`/api/admin/me/permissions?admin_username=${encodeURIComponent(username)}`);
  report.records.admin_apis = {
    passed: [dashboard, operations, usageSummary, usageTrend, permissions].every((item) => item.status >= 200 && item.status < 300),
    statuses: { dashboard: dashboard.status, operations: operations.status, usage_summary: usageSummary.status, usage_trend: usageTrend.status, permissions: permissions.status },
  };

  const homeCards = await page.locator(".admin-dashboard-stat").allTextContents();
  const homeText = await page.locator("body").innerText();
  const overview = dashboard.body?.overview || {};
  const userCard = homeCards.find((item) => item.includes("用户总数")) || "";
  const courseCard = homeCards.find((item) => item.includes("课程总数")) || "";
  report.records.dashboard_load = { passed: homeCards.length === 4, card_count: homeCards.length };
  report.records.user_metrics = { passed: userCard.includes(formatNumber(overview.total_users)), api_total_users: overview.total_users, ui_card: userCard };
  report.records.learning_metrics = { passed: courseCard.includes(formatNumber(overview.total_courses)), api_total_courses: overview.total_courses, ui_card: courseCard };
  const homeScreenshot = screenshotPath("admin-dashboard-home.png");
  report.records.dashboard_screenshot = { passed: true, path: homeScreenshot };
  await page.screenshot({ path: homeScreenshot, fullPage: false });

  await clickNav("订单管理", "暂无订单数据");
  const ordersText = await page.locator("body").innerText();
  report.records.order_revenue_empty_state = {
    passed: ordersText.includes("暂无订单数据") && ordersText.includes("未接入真实订单") && !ordersText.includes("总营收"),
    explicit_empty_state: ordersText.includes("暂无订单数据"),
    no_revenue_card: !ordersText.includes("总营收"),
  };
  await page.screenshot({ path: screenshotPath("admin-dashboard-orders-empty.png"), fullPage: false });

  await clickNav("数据统计", "近 7 天 AI 调用趋势");
  await page.waitForFunction(
    ({ label, value }) => document.body.innerText.includes(label) && document.body.innerText.includes(value),
    { label: "今日调用", value: formatNumber(usageSummary.body?.today_total) },
    { timeout: 30000 },
  );
  const statisticsText = await page.locator("body").innerText();
  const trendItems = Array.isArray(usageTrend.body?.items) ? usageTrend.body.items : [];
  const trendChart = page.locator("svg.admin-dashboard-chart");
  const trendLabels = await trendChart.evaluate((element) => Array.from(element.querySelectorAll("text")).map((item) => item.textContent || ""));
  const visibleTrendDate = trendItems.some((item) => item.date && trendLabels.includes(String(item.date).slice(5)));
  report.records.ai_metrics = { passed: statisticsText.includes("今日调用") && statisticsText.includes(formatNumber(usageSummary.body?.today_total)), api_today_total: usageSummary.body?.today_total };
  report.records.real_trend_chart = { passed: trendItems.length === 7 && visibleTrendDate, api_days: trendItems.length, visible_date: visibleTrendDate, visible_labels: trendLabels };
  await page.screenshot({ path: screenshotPath("admin-dashboard-statistics-trend.png"), fullPage: false });

  await clickNav("AI 用量统计", "AI 用量统计");
  await page.screenshot({ path: screenshotPath("admin-dashboard-ai-usage.png"), fullPage: false });

  await page.evaluate(() => localStorage.setItem("ai_study_current_page", "adminCenter"));
  await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByText("AI 使用概览", { exact: true }).first().waitFor({ state: "visible", timeout: 30000 });
  const centerText = await page.locator("body").innerText();
  report.records.ai_estimated_cost_wording = {
    passed: centerText.includes("估算成本") && !centerText.includes("实际支出"),
    has_estimated_label: centerText.includes("估算成本"),
    has_actual_spend_label: centerText.includes("实际支出"),
  };
  await page.screenshot({ path: screenshotPath("admin-center-overview.png"), fullPage: false });

  const forbiddenGrowth = /(12\.5%|8\.3%|15\.7%|9\.4%|4\.6%|11\.3%|较昨日|较上周)/;
  report.records.no_hardcoded_growth = { passed: !forbiddenGrowth.test(homeText) && !forbiddenGrowth.test(statisticsText) && !forbiddenGrowth.test(centerText) };
  report.records.console = { passed: report.console_business_errors.length === 0, business_errors: report.console_business_errors.length };
  report.records.network = { passed: report.unexpected_network_failures.length === 0, failures: report.unexpected_network_failures.length };
  report.status = Object.values(report.records).every((record) => record?.passed !== false) ? "passed" : "failed";
}

try {
  await main();
} catch (error) {
  report.status = "failed";
  report.error = String(error?.message || error).slice(0, 800);
  if (page) {
    report.failure_page_url = page.url();
    const failurePath = screenshotPath("admin-dashboard-failure.png");
    await page.screenshot({ path: failurePath, fullPage: false }).catch(() => {});
  }
} finally {
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  if (context) await context.close().catch(() => {});
  if (browser) await browser.close().catch(() => {});
}

console.log(JSON.stringify({
  status: report.status,
  report_path: "verification-results/admin-dashboard-production/acceptance-final.json",
  screenshots: report.screenshots,
  console_business_errors: report.console_business_errors.length,
  unexpected_network_failures: report.unexpected_network_failures.length,
}));
process.exitCode = report.status === "passed" ? 0 : 1;
