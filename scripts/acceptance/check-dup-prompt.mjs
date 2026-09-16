import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const FILE = "C:/Users/26477/Desktop/课程文件/大二上/数据库/第一章-20260824/ch06.pptx";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3000);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3500);
}
await page.locator(".eh-subject-tile", { hasText: "数据结构" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
// upload the already-existing ch06.pptx (should trigger duplicate)
await page.locator("input[type=file]").first().setInputFiles(FILE).catch(() => {});
await page.waitForTimeout(4000);
// capture the tip message
const tip = await page.evaluate(() => {
  const els = Array.from(document.querySelectorAll("[class*=tip], [class*=message], [class*=error], [class*=notice]"));
  return els.map(e => e.innerText.trim()).filter(t => t.includes("已上传") || t.includes("已存在") || t.includes("无需重复") || t.includes("失败")).slice(0,5);
});
console.log("TIP/ERROR:", JSON.stringify(tip));
await browser.close();
