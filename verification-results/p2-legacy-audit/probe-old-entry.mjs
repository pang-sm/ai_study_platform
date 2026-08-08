import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const baseUrl = "http://101.32.190.42/";
const authState = path.resolve(root, ".playwright/.auth/programming-workbench-online.json");
const outputDir = path.resolve(root, "verification-results/p2-legacy-audit");
const screenshot = path.join(outputDir, "old-entry-click.png");
const reportPath = path.join(outputDir, "old-entry-click.json");
fs.mkdirSync(outputDir, { recursive: true });

const result = {
  audit: "p2-legacy-programming-old-entry",
  base_url: baseUrl,
  auth_state_supplied: fs.existsSync(authState),
  storage_state_written_to_report: false,
  legacy_state: "ai_study_current_page=codeStudio",
  console_errors: [],
  failed_network: [],
  steps: {},
};

let browser;
let page = null;
try {
  if (!fs.existsSync(authState)) throw new Error("verified auth state is missing");
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ storageState: authState, viewport: { width: 1440, height: 900 } });
  await context.addInitScript(() => {
    try { localStorage.setItem("ai_study_current_page", "codeStudio"); } catch {}
  });
  await context.route("**/*", async (route) => {
    const url = route.request().url().toLowerCase();
    if (url.includes("statsig") || url.includes("ab.chatgpt.com") || url.includes("telemetry") || url.includes("analytics")) return route.abort();
    return route.continue();
  });
  page = await context.newPage();
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) result.console_errors.push({ type: message.type(), text: message.text().slice(0, 500) });
  });
  page.on("pageerror", (error) => result.console_errors.push({ type: "pageerror", text: String(error.message || error).slice(0, 500) }));
  page.on("response", (response) => {
    const status = response.status();
    const url = response.url();
    if (status >= 400 && /\/api\//.test(url) && !/statsig|telemetry|analytics/.test(url)) {
      result.failed_network.push({ status, url: url.replace(/([?&]username=)[^&]+/i, "$1<redacted>") });
    }
  });

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.locator(".ph-page").waitFor({ state: "visible", timeout: 30000 });
  result.steps.stale_page_migration = {
    passed: true,
    url: page.url(),
    programming_home_count: await page.locator(".ph-page").count(),
    legacy_code_studio_count: await page.locator(".code-studio-shell").count(),
    legacy_sidebar_count: await page.locator(".fig2-sidebar").count(),
  };
  result.steps.legacy_entry_hidden = {
    passed: (await page.locator(".fig2-sidebar").count()) === 0 && (await page.locator(".code-studio-shell").count()) === 0,
  };
  await page.screenshot({ path: screenshot, fullPage: false });
  result.screenshot = path.relative(root, screenshot).replaceAll("\\", "/");
  result.status = result.steps.legacy_entry_hidden.passed ? "stale_state_migrated" : "legacy_reachable";
} catch (error) {
  result.status = "probe_failed";
  result.error = String(error?.message || error).slice(0, 800);
  if (typeof page !== "undefined" && page) {
    result.page_url = page.url();
    result.page_title = await page.title().catch(() => "");
    result.body_excerpt = (await page.locator("body").innerText({ timeoutMs: 3000 }).catch(() => "")).slice(0, 1000);
    try {
      await page.screenshot({ path: screenshot, fullPage: false });
      result.screenshot = path.relative(root, screenshot).replaceAll("\\", "/");
    } catch {}
  }
} finally {
  if (browser) await browser.close().catch(() => {});
  fs.writeFileSync(reportPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify(result, null, 2));
process.exitCode = result.status === "stale_state_migrated" ? 0 : 1;
