import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
// click 计算机组成原理 course
await page.locator(".clh-course-main", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
console.log("after course click URL:", page.url());
// click 资料库
await page.getByText("资料库", { exact: true }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3500);
console.log("after 资料库 URL:", page.url());
const files = await page.evaluate(() => Array.from(document.querySelectorAll("tbody tr td:first-child")).map(t => t.innerText.trim()).filter(Boolean));
console.log("visible files:", JSON.stringify(files));
// Ctrl+F5
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000);
console.log("after Ctrl+F5 URL:", page.url());
console.log("body head:", (await body()).slice(0, 200));
await browser.close();
