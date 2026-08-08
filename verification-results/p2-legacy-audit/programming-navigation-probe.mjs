import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const baseUrl = "http://101.32.190.42/";
const authState = path.resolve(root, ".playwright/.auth/programming-workbench-online.json");
const outputDir = path.resolve(root, "verification-results/p2-legacy-audit");
const reportPath = path.join(outputDir, "programming-navigation.json");
const screenshotDir = path.join(outputDir, "screenshots");
fs.mkdirSync(screenshotDir, { recursive: true });

const targets = [
  { language: "Python", exerciseId: 1629 },
  { language: "C++", exerciseId: 1734 },
  { language: "Java", exerciseId: 1546 },
];

const result = {
  audit: "p2-programming-navigation",
  base_url: baseUrl,
  auth_state_supplied: fs.existsSync(authState),
  targets,
  records: {},
  console_errors: [],
  failed_network: [],
  status: "not_started",
};

function isLibraryResponse(response, language, pageNumber) {
  try {
    const url = new URL(response.url());
    return response.status() === 200
      && url.pathname.endsWith("/api/programming/exercises")
      && url.searchParams.get("language") === language
      && Number(url.searchParams.get("page") || 1) === pageNumber;
  } catch {
    return false;
  }
}

async function waitForLibrary(page, language, pageNumber, action) {
  const response = page.waitForResponse((item) => isLibraryResponse(item, language, pageNumber), { timeout: 30000 });
  await action();
  await response;
  await page.locator(".ph-exercise-card").first().waitFor({ state: "visible", timeout: 30000 });
}

let browser;
try {
  if (!result.auth_state_supplied) throw new Error("verified auth state is missing");
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ storageState: authState, viewport: { width: 1440, height: 900 } });
  await context.route("**/*", async (route) => {
    const url = route.request().url().toLowerCase();
    if (url.includes("statsig") || url.includes("ab.chatgpt.com") || url.includes("telemetry") || url.includes("analytics")) return route.abort();
    return route.continue();
  });
  const page = await context.newPage();
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) result.console_errors.push({ type: message.type(), text: message.text().slice(0, 500) });
  });
  page.on("pageerror", (error) => result.console_errors.push({ type: "pageerror", text: String(error.message || error).slice(0, 500) }));
  page.on("response", (response) => {
    const status = response.status();
    if (status >= 400 && /\/api\//.test(response.url()) && !/statsig|telemetry|analytics/.test(response.url())) {
      result.failed_network.push({ status, url: response.url().replace(/([?&]username=)[^&]+/i, "$1<redacted>") });
    }
  });

  await page.goto(baseUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.locator(".ph-page").waitFor({ state: "visible", timeout: 30000 });

  for (const target of targets) {
    const record = { language: target.language, exercise_id: target.exerciseId, steps: {} };
    result.records[target.language] = record;

    await page.locator(".ph-nav button").nth(3).click();
    await page.locator(".ph-exercise-panel").waitFor({ state: "visible", timeout: 30000 });
    const languageButton = page.locator(".ph-exercise-filters:not(.ph-exercise-status-filters) button").filter({ hasText: target.language }).first();
    const activeLanguage = await page.locator(".ph-exercise-filters:not(.ph-exercise-status-filters) button.is-active").first().innerText().catch(() => "");
    if (activeLanguage.trim() !== target.language) {
      await waitForLibrary(page, target.language, 1, () => languageButton.click());
    } else {
      await page.locator(".ph-exercise-card").first().waitFor({ state: "visible", timeout: 30000 });
    }
    await page.locator(".ph-exercise-filters:not(.ph-exercise-status-filters) button.is-active").filter({ hasText: target.language }).waitFor({ state: "visible", timeout: 12000 });
    await page.locator(".ph-exercise-status-filters select").nth(2).selectOption("48");
    await page.locator(".ph-exercise-card").first().waitFor({ state: "visible", timeout: 30000 });

    const pageData = await page.evaluate(async (language) => {
      const response = await fetch(`/api/programming/exercises?language=${encodeURIComponent(language)}&page=1&page_size=48`);
      const data = await response.json();
      return { total: Number(data.total || 0), ids: (data.exercises || []).map((item) => Number(item.id)) };
    }, target.language);
    let pageNumber = 1;
    let targetIndex = pageData.ids.indexOf(target.exerciseId);
    if (targetIndex < 0) {
      pageNumber = 2;
      const nextButton = page.locator(".ph-pagination button").nth(1);
      await waitForLibrary(page, target.language, 2, () => nextButton.click());
      const secondPage = await page.evaluate(async (language) => {
        const response = await fetch(`/api/programming/exercises?language=${encodeURIComponent(language)}&page=2&page_size=48`);
        const data = await response.json();
        return (data.exercises || []).map((item) => Number(item.id));
      }, target.language);
      targetIndex = secondPage.indexOf(target.exerciseId);
    }
    if (targetIndex < 0) throw new Error(`${target.language} exercise ${target.exerciseId} is not in the visible approved library`);

    const card = page.locator(".ph-exercise-card").nth(targetIndex);
    await card.waitFor({ state: "visible", timeout: 12000 });
    const startResponse = page.waitForResponse((response) => response.status() === 200 && new URL(response.url()).pathname.endsWith(`/api/programming/exercises/${target.exerciseId}/start`), { timeout: 30000 });
    await card.locator("button").click();
    await startResponse;
    await page.locator(".pw-shell").waitFor({ state: "visible", timeout: 30000 });
    await page.locator(`.pw-current-language`).filter({ hasText: target.language }).waitFor({ state: "visible", timeout: 12000 });
    await page.locator(".pw-back-to-programming").waitFor({ state: "visible", timeout: 12000 });
    record.steps.open_from_library = { passed: true, page: pageNumber, card_index: targetIndex };
    await page.screenshot({ path: path.join(screenshotDir, `navigation-${target.language.replaceAll("+", "p").toLowerCase()}-workbench.png`) });

    await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator(".pw-shell").waitFor({ state: "visible", timeout: 30000 });
    await page.locator(".pw-back-to-programming").waitFor({ state: "visible", timeout: 12000 });
    record.steps.refresh_restored_workbench = { passed: true };

    await page.locator(".pw-back-to-programming").click();
    await page.locator(".ph-page").waitFor({ state: "visible", timeout: 30000 });
    await page.locator(".ph-hero").waitFor({ state: "visible", timeout: 12000 });
    record.steps.back_to_programming_home = { passed: true, legacy_code_studio_count: await page.locator(".code-studio-shell").count() };
  }

  result.status = Object.values(result.records).every((item) => Object.values(item.steps).every((step) => step.passed))
    && result.console_errors.length === 0 && result.failed_network.length === 0
    ? "passed"
    : "failed";
} catch (error) {
  result.status = "failed";
  result.error = String(error?.message || error).slice(0, 800);
} finally {
  if (browser) await browser.close().catch(() => {});
  fs.writeFileSync(reportPath, `${JSON.stringify(result, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify(result, null, 2));
process.exitCode = result.status === "passed" ? 0 : 1;
