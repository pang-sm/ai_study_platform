// P0-B E2E (part 2): big/综合题 display + submit, chapter back, 3-viewport screenshots.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000";
const SUBJECT = "computer_organization";
const USER = `mobile_v164_pbbig_${Date.now()}`;
const PASS = "v164big12345";
const SHOT_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../verification-results/mobile-v164-p0b");
fs.mkdirSync(SHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const api = ctx.request;
const results = [];
const check = (name, ok, extra = "") => { results.push([name, ok]); console.log(`${ok ? "PASS" : "FAIL"} ${name}${extra ? " — " + extra : ""}`); };

try {
  await api.post(`${API}/register`, { data: { username: USER, password: PASS } });
  const page = await ctx.newPage();
  await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.evaluate((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify({ username: u, nickname: "P0B-BIG", onboarding_completed: true })), USER);

  // Direct to chapter practice with a pre-selected knowledge scope (1.1 has big questions)
  await page.goto(`${WEB}/m/exam11408/${SUBJECT}/practice?type=chapter&knowledgeId=1.1&knowledge=%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%B3%BB%E7%BB%9F%E6%A6%82%E8%BF%B0`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2200);
  const scopeShown = await page.locator(".v16-selected-range").isVisible().catch(() => false);
  check("chapter practice pre-selects scope from route", scopeShown);
  await page.locator(".v16-selected-range .primary-button").first().click();
  await page.waitForTimeout(3000);

  // big question display
  const bigMeta = page.locator(".mobile-question-meta", { hasText: "综合题" }).first();
  const bigVisible = await bigMeta.isVisible().catch(() => false);
  check("big question shows 综合题 label", bigVisible);
  const bigTextarea = page.locator(".mobile-practice-question", { hasText: "综合题" }).first().locator("textarea.mobile-answer-input");
  const textareaVisible = await bigTextarea.isVisible().catch(() => false);
  check("big question renders a textarea", textareaVisible);
  if (textareaVisible) {
    await bigTextarea.fill("计算机系统由硬件和软件组成，硬件包括运算器、控制器、存储器、输入输出设备。");
    await page.screenshot({ path: path.join(SHOT_DIR, "04-chapter-big.png") }).catch(() => {});
  }

  // submit (choice auto-graded, big self-review)
  await page.locator("button.primary-button", { hasText: "提交" }).first().click();
  await page.waitForTimeout(3000);
  const resultVisible = await page.locator(".practice-result-v14").first().isVisible().catch(() => false);
  check("chapter submit shows result", resultVisible);
  const selfReviewShown = await page.locator(".practice-result-v14", { hasText: "待自评" }).first().isVisible().catch(() => false);
  const refAnswerShown = await page.locator(".practice-result-v14", { hasText: "参考答案" }).first().isVisible().catch(() => false);
  check("big result shows 待自评 (self-review)", selfReviewShown);
  check("big result shows 参考答案", refAnswerShown);
  await page.screenshot({ path: path.join(SHOT_DIR, "07-past-paper-result.png") }).catch(() => {});

  // chapter back button → practice home
  await page.locator(".v16-practice-header button", { hasText: "返回" }).first().click();
  await page.waitForTimeout(1000);
  const homeVisible = await page.getByText("章节练习").first().isVisible().catch(() => false) || await page.getByText("AI出题").first().isVisible().catch(() => false);
  check("chapter practice back → practice home", homeVisible);

  // 3-viewport screenshots of practice home
  for (const vp of [{ w: 360, h: 800 }, { w: 390, h: 844 }, { w: 412, h: 915 }]) {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await page.goto(`${WEB}/m/exam11408/${SUBJECT}/practice`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(1200);
    await page.screenshot({ path: path.join(SHOT_DIR, `viewport-${vp.w}x${vp.h}.png`) }).catch(() => {});
  }
} catch (e) {
  console.error("FATAL", e.message);
} finally {
  await browser.close();
  const allPass = results.every(([, ok]) => ok);
  console.log(`\n===== P0-B BIG RESULT =====  PASS=${allPass}  (${results.filter(([, ok]) => ok).length}/${results.length})`);
  console.log(`TEST_USER=${USER}`);
}
