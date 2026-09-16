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

async function switchTo(label, btn) {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.getByText(btn, { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3500);
  }
}

await switchTo("11408", "切换到 11408");
let t = await body();
console.log("11408 首页:", t.includes("11408 备考") || t.includes("欢迎回来") ? "OK" : "FAIL", "| 全程考包:", t.includes("全程考包"));

await switchTo("course", "切换到课程");
t = await body();
console.log("课程学习首页:", t.includes("课程学习") ? "OK" : "FAIL");

await switchTo("programming", "切换到编程");
t = await body();
console.log("编程学习首页:", t.includes("编程学习") ? "OK" : "FAIL");

// 商城
const cat = await ctx.request.get(`${BASE}/api/membership/catalog?service_key=exam_11408`);
console.log("商城 catalog:", cat.status() === 200 ? "OK" : "FAIL");

await browser.close();
