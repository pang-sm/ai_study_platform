import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2200);
await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3800);
await page.locator(".eh-subject-tile", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2800);
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3200);
// dump the stats row values and the material list
const statValues = await page.evaluate(() => {
  return Array.from(document.querySelectorAll(".cmp-stat-card")).map(c => ({
    value: c.querySelector(".cmp-stat-value")?.innerText || "",
    label: c.querySelector(".cmp-stat-label")?.innerText || "",
    valueOverflow: (() => { const el = c.querySelector(".cmp-stat-value"); return el ? el.scrollWidth > el.clientWidth : false; })(),
  }));
});
console.log("STAT CARDS:", JSON.stringify(statValues, null, 2));
const files = await page.evaluate(() => Array.from(document.querySelectorAll("tbody tr td:first-child")).map(t => t.innerText.trim()).filter(Boolean));
console.log("FILES:", JSON.stringify(files));
await browser.close();
