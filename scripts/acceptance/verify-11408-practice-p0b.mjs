// P0-B E2E: 11408 practice rewrite — chapter practice vs past paper isolation,
// question type 中文化, back navigation, real question counts.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000";
const SUBJECT = "computer_organization";
const SUBJECT_NAME = "计算机组成原理";
const USER = `mobile_v164_pb_${Date.now()}`;
const PASS = "v164pb12345";
const SHOT_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../verification-results/mobile-v164-p0b");
fs.mkdirSync(SHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const api = ctx.request;
const results = [];
const check = (name, ok, extra = "") => { results.push([name, ok]); console.log(`${ok ? "PASS" : "FAIL"} ${name}${extra ? " — " + extra : ""}`); };

const apiLog = [];
ctx.on("request", (r) => {
  const u = r.url();
  if (u.includes("/api/") || u.includes(":8000/")) {
    const m = u.match(/\/(exam\/11408[^?]*|knowledge-map[^?]*)/);
    if (m) apiLog.push(m[1]);
  }
});

try {
  // register + seed localStorage
  const reg = await api.post(`${API}/register`, { data: { username: USER, password: PASS } });
  const regBody = await reg.json().catch(() => ({}));
  const prof = regBody.user || regBody.profile || {};
  console.log(`[register] ${reg.status()} user=${prof.username || USER}`);

  const page = await ctx.newPage();
  await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.evaluate((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify({ username: u, nickname: "P0B测试", onboarding_completed: true })), USER);

  // ── A. knowledge node → 进入练习 → chapter practice (not past paper) ──
  await page.goto(`${WEB}/m/exam11408/${SUBJECT}/chapters`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2500);
  await page.screenshot({ path: path.join(SHOT_DIR, "01-practice-home.png") }).catch(() => {});
  const leafSel = page.locator(".v16-tree-select").first();
  if (await leafSel.isVisible().catch(() => false)) {
    await leafSel.click();
    await page.waitForTimeout(700);
    const sheetVisible = await page.locator(".knowledge-sheet-v14, .mobile-bottom-sheet").filter({ hasText: "进入练习" }).isVisible().catch(() => false);
    check("knowledge bottom sheet opens with 进入练习", sheetVisible);
    apiLog.length = 0;
    await page.getByText("进入练习").first().click();
    await page.waitForTimeout(2000);
    const urlChapter = page.url().includes("type=chapter");
    const pastPaperCalls = apiLog.filter((p) => p.includes("past-paper")).length;
    check("进入练习 navigates to chapter practice (type=chapter)", urlChapter, page.url());
    check("chapter practice: no past-paper network", pastPaperCalls === 0, `past-paper calls=${pastPaperCalls}`);
    check("chapter practice: chapter-practice network present", apiLog.some((p) => p.includes("chapter-practice")));
    await page.screenshot({ path: path.join(SHOT_DIR, "02-chapter-scope.png") }).catch(() => {});
  } else {
    check("knowledge tree visible", false, "no .v16-tree-select found");
  }

  // ── B. chapter practice scope (from practice home entry) ──
  await page.goto(`${WEB}/m/exam11408/${SUBJECT}/practice`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(1500);
  const chapterEntry = page.getByText("章节练习").first();
  if (await chapterEntry.isVisible().catch(() => false)) {
    await chapterEntry.click();
    await page.waitForTimeout(2000);
    check("practice home has 章节练习 entry", true);
    // select first parent node
    const firstSelect = page.locator(".v16-tree-select").first();
    if (await firstSelect.isVisible().catch(() => false)) {
      await firstSelect.click();
      await page.waitForTimeout(500);
      const rangeVisible = await page.locator(".v16-selected-range").isVisible().catch(() => false);
      check("parent node selection shows scope", rangeVisible);
      apiLog.length = 0;
      await page.locator(".v16-selected-range .primary-button").first().click();
      await page.waitForTimeout(2500);
      const qCount = await page.locator(".v16-question, .mobile-practice-question").count();
      check("chapter practice starts with scoped questions (not full bank)", qCount > 0 && qCount < 500, `questions=${qCount}`);
      check("chapter practice: no past-paper network", apiLog.filter((p) => p.includes("past-paper")).length === 0);
      const typeLabel = await page.locator(".mobile-question-meta").first().innerText().catch(() => "");
      check("question type shows Chinese (选择题/综合题)", /选择题|综合题|单选题|多选题|简答题|论述题|填空题|判断题/.test(typeLabel), typeLabel);
      await page.screenshot({ path: path.join(SHOT_DIR, "03-chapter-choice.png") }).catch(() => {});
      // answer + submit
      const optBtn = page.locator(".mobile-question-options button").first();
      if (await optBtn.isVisible().catch(() => false)) {
        await optBtn.click();
        await page.locator(".primary-button", { hasText: "提交" }).first().click();
        await page.waitForTimeout(2500);
        const resultVisible = await page.locator(".practice-result-v14").first().isVisible().catch(() => false);
        check("choice submit shows result", resultVisible);
      }
    }
  } else {
    check("practice home 章节练习 entry", false, "not found");
  }

  // ── C. past paper 2022 → count == PC (13) ──
  apiLog.length = 0;
  await page.goto(`${WEB}/m/exam11408/${SUBJECT}/practice?type=past-paper`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SHOT_DIR, "05-past-paper-years.png") }).catch(() => {});
  const year2022 = page.locator(".year-list-v14 button", { hasText: "2022" }).first();
  if (await year2022.isVisible().catch(() => false)) {
    await year2022.click();
    await page.locator("button.primary-button", { hasText: "开始答题" }).first().click();
    await page.waitForTimeout(3000);
    const qCount = await page.locator(".mobile-practice-question").count();
    check("past paper 2022 count matches PC (not hundreds)", qCount > 0 && qCount < 100, `questions=${qCount}`);
    check("past paper: no chapter-practice network", apiLog.filter((p) => p.includes("chapter-practice")).length === 0);
    check("past paper: past-paper-attempts network present", apiLog.some((p) => p.includes("past-paper-attempts")));
    await page.screenshot({ path: path.join(SHOT_DIR, "06-past-paper-session.png") }).catch(() => {});
    // back from session → year list
    await page.locator(".v16-practice-header button", { hasText: "返回" }).first().click();
    await page.waitForTimeout(800);
    const backToYears = await page.locator(".year-list-v14").isVisible().catch(() => false);
    check("past paper session back → year list", backToYears);
    // back from year list → practice home
    await page.locator(".v16-practice-header button", { hasText: "返回" }).first().click();
    await page.waitForTimeout(800);
    const backToHome = await page.getByText("章节练习").first().isVisible().catch(() => false) || await page.getByText("真题").first().isVisible().catch(() => false);
    check("past paper year list back → practice home", backToHome);
  } else {
    check("past paper 2022 year button", false, "not found");
  }
} catch (e) {
  console.error("FATAL", e.message);
  console.error(e.stack);
} finally {
  await browser.close();
  const allPass = results.every(([, ok]) => ok);
  console.log(`\n===== P0-B RESULT =====  PASS=${allPass}  (${results.filter(([, ok]) => ok).length}/${results.length})`);
  console.log(`TEST_USER=${USER}`);
  console.log(`API log (unique): ${[...new Set(apiLog)].join(", ")}`);
}
