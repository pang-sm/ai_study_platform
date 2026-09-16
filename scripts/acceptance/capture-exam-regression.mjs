import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const netLog = [];
page.on("request", (req) => { const u = req.url(); if (u.includes("/api/materials")) netLog.push({ type:"req", method:req.method(), url:u }); });
page.on("response", async (res) => { const u = res.url(); if (u.includes("/api/materials") && res.request().method()==="GET") { try { const j = await res.json(); netLog.push({ type:"list", url:u, total:j?.materials?.length, ids:(j?.materials||[]).map(m=>m.id) }); } catch {} } });

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
// enter 计组
await page.locator(".eh-subject-tile", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2800);
// 资料库
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3500);
console.log("exam materials URL:", page.url());
const visibleFiles = await page.evaluate(() => Array.from(document.querySelectorAll("tbody tr td:first-child")).map(t => t.innerText.trim()).filter(Boolean));
console.log("visible files in table:", JSON.stringify(visibleFiles));
console.log("===== NETWORK =====");
for (const l of netLog) console.log(JSON.stringify(l));
await browser.close();
