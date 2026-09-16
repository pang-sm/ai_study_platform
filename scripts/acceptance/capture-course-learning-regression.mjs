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
const netLog = [];
page.on("request", (req) => {
  const u = req.url();
  if (u.includes("/api/materials")) netLog.push({ type: "req", method: req.method(), url: u, postData: req.postData() || "" });
});
page.on("response", async (res) => {
  const u = res.url();
  if (u.includes("/api/materials") && !u.includes("/upload") && res.request().method() === "GET") {
    try { const j = await res.json(); netLog.push({ type: "listResp", url: u, status: res.status(), total: j?.materials?.length, ids: (j?.materials||[]).map(m => m.id) }); } catch {}
  }
  if (u.includes("/api/materials/upload")) {
    try { const j = await res.json(); netLog.push({ type: "uploadResp", status: res.status(), body: j }); } catch {}
  }
});

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
console.log("course home URL:", page.url());

// Click the 计算机组成原理 course card
const card = page.locator(".clh-course-main", { hasText: "计算机组成原理" }).first();
await card.click({ timeout: 15000 }).catch((e) => console.log("course card click err", e.message));
await page.waitForTimeout(3500);
console.log("after course URL:", page.url());

// Click 资料库 in the course dashboard sidebar
await page.locator("[data-tour='course-materials'], .csd-nav-item", { hasText: "资料库" }).first().click({ timeout: 10000 }).catch(async () => {
  await page.getByText("资料库", { exact: true }).first().click({ timeout: 10000 }).catch((e) => console.log("资料库 click err", e.message));
});
await page.waitForTimeout(3500);
console.log("after 资料库 URL:", page.url());

// Upload a test PDF
const pdfPath = path.join(PROJECT_ROOT, "verification-screenshots", "11408-scope", "scope-11408-coa-final-20260827181345.pdf");
if (fs.existsSync(pdfPath)) {
  await page.locator("input[type=file]").first().setInputFiles(pdfPath).catch((e) => console.log("upload err", e.message));
  await page.waitForTimeout(4000);
  console.log("after upload URL:", page.url());
}

console.log("\n===== NETWORK LOG =====");
for (const l of netLog) console.log(JSON.stringify(l));
await browser.close();
