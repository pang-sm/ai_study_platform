import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT = path.join(PROJECT_ROOT, "verification-screenshots", "11408-round3");
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
// On exam home now, click the user card (data-tour="exam-profile") to open profile
await page.locator("[data-tour='exam-profile']").first().click({ timeout: 15000 }).catch(async () => {
  await page.locator(".eh-user-card").first().click({ timeout: 15000 }).catch(() => {});
});
await page.waitForTimeout(4000);
let t = await body();
console.log("URL:", page.url());
console.log("has 考试时间:", t.includes("考试时间"), "| has 当前备考阶段:", t.includes("当前备考阶段"), "| has 每天学习时间:", t.includes("每天学习时间"));
const reg = t.match(/注册时间\s*([0-9]{4}-[0-9]{2}-[0-9]{2})/);
console.log("注册时间:", reg ? reg[1] : "NOT FOUND", "| 含完整时间戳:", /T\d{2}:\d{2}/.test(t));
console.log("has 编辑资料:", t.includes("编辑资料"));
console.log("has 冲刺阶段:", t.includes("冲刺阶段"), "| has 6 - 8 小时:", t.includes("6 - 8 小时"));
await page.screenshot({ path: path.join(SHOT, "profile-final.png") }).catch(() => {});
await browser.close();
