import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT = path.join(PROJECT_ROOT, "verification-screenshots", "11408-round3");
fs.mkdirSync(SHOT, { recursive: true });
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);
const shot = (n) => page.screenshot({ path: path.join(SHOT, n + ".png") }).catch(() => {});

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}

// 章节练习 (数据结构)
await page.locator(".eh-subject-tile", { hasText: "数据结构" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);
await page.locator(".exam-subject-nav-item", { hasText: "练习中心" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(4000);
let t = await body();
const cardTxt = await page.evaluate(() => {
  const el = Array.from(document.querySelectorAll(".practice-type-card")).find(c => c.innerText.includes("章节练习"));
  return el ? el.innerText.replace(/\s+/g, " ").slice(0, 80) : "NOT FOUND";
});
console.log("章节练习卡片:", cardTxt);
console.log("has 题目待录入:", t.includes("题目待录入"));
console.log("has 道题:", /\d+ 道题/.test(t));
await shot("chapter-practice-ds");

// 四科 count 抽查（直接 API）
for (const s of ["computer_organization", "operating_system", "computer_network"]) {
  const r = await ctx.request.get(`${BASE}/api/exam/11408/${s}/chapter-practice/questions?username=${encodeURIComponent("奶12")}`);
  const j = await r.json().catch(() => ({}));
  console.log(s, "total", j.total);
}

// 个人资料 (回到学科 home，点右上角头像按钮)
await page.getByText("首页", { exact: true }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(2500);
await page.locator(".exam-subject-profile").first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(4000);
t = await body();
console.log("\n=== 个人资料 ===");
console.log("has 考试时间:", t.includes("考试时间"), "| has 当前备考阶段:", t.includes("当前备考阶段"), "| has 每天学习时间:", t.includes("每天学习时间"));
const reg = t.match(/注册时间\s*([0-9]{4}-[0-9]{2}-[0-9]{2})/);
console.log("注册时间:", reg ? reg[1] : "NOT FOUND", "| 含完整时间戳:", /T\d{2}:\d{2}/.test(t));
console.log("has 编辑资料:", t.includes("编辑资料"));
await shot("profile-exam-info");

await browser.close();
console.log("DONE");
