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
await page.waitForTimeout(3000);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3500);
}
console.log("course home URL:", page.url());
await page.locator(".clh-user-card").first().click({ timeout: 15000 }).catch((e) => console.log("user-card err", e.message));
await page.waitForTimeout(3500);
console.log("profile URL:", page.url());
const t = await page.evaluate(() => document.body.innerText);
const idx = t.indexOf("账号安全");
console.log("账号安全 section:", idx >= 0 ? t.slice(idx, idx+200).replace(/\n+/g," | ") : "NOT FOUND");
await browser.close();
