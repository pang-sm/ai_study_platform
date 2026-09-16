import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);

async function switchToExam() {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3200);
  if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2200);
    await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3800);
  }
}

// 章节练习卡片
await switchToExam();
await page.locator(".eh-subject-tile", { hasText: "数据结构" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);
// click practice nav item (sidebar)
await page.locator(".exam-subject-nav-item", { hasText: "练习中心" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3500);
let t = await body();
const idx = t.indexOf("题目待录入");
console.log("题目待录入 index:", idx);
if (idx >= 0) console.log("context:", JSON.stringify(t.slice(Math.max(0, idx-40), idx+40)));
// find chapter card text
const card = await page.evaluate(() => {
  const els = Array.from(document.querySelectorAll(".practice-type-card"));
  return els.map(e => e.innerText.replace(/\s+/g, " ").slice(0, 60));
});
console.log("CARDS:", JSON.stringify(card));

// 个人资料
console.log("\n=== 个人资料 ===");
await page.locator(".exam-subject-profile").first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3500);
t = await body();
console.log("profile URL:", page.url());
console.log("has 考试时间:", t.includes("考试时间"));
const reg = t.match(/注册时间[\s\S]{0,20}?(\d{4}-\d{2}-\d{2})/);
console.log("注册时间:", reg ? reg[1] : "NOT FOUND", "| full ts:", /T\d{2}:\d{2}/.test(t));
console.log("has 编辑资料:", t.includes("编辑资料"));
await browser.close();
