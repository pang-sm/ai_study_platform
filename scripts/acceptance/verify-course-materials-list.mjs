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
const netLog = [];
page.on("request", (req) => { const u = req.url(); if (u.includes("/api/materials")) netLog.push({ method: req.method(), url: u }); });

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
await page.locator(".clh-course-main", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
// click 资料库 via csd-nav-item
await page.locator(".csd-nav-item", { hasText: "资料库" }).first().click({ timeout: 10000 }).catch((e) => console.log("资料库 click err", e.message));
await page.waitForTimeout(3500);
console.log("materials URL:", page.url());
const files = await page.evaluate(() => Array.from(document.querySelectorAll("tbody tr td:first-child")).map(t => t.innerText.trim()).filter(Boolean));
console.log("visible files:", JSON.stringify(files));
console.log("has 资料库 title/upload:", (await body()).includes("上传课程资料"), (await body()).includes("资料总数"));
console.log("===== NETWORK =====");
for (const l of netLog) console.log(JSON.stringify(l));
await browser.close();
