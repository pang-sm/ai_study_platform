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
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3000);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3500);
}
await page.locator("[data-tour='exam-profile']").first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3500);
let t = await body();
console.log("has 绑定手机号:", t.includes("绑定手机号"), "| has 未绑定:", t.includes("未绑定"));
// click 绑定手机号 button
await page.getByRole("button", { name: "绑定手机号" }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(800);
t = await body();
console.log("modal has +86:", t.includes("+86"), "| has 获取验证码:", t.includes("获取验证码"), "| has 确认绑定:", t.includes("确认绑定"));
await page.screenshot({ path: path.join(PROJECT_ROOT, "verification-screenshots", "phase-b-phone-modal.png") }).catch(() => {});
await browser.close();
