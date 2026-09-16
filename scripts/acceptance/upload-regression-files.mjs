import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const dir = path.join(PROJECT_ROOT, "verification-screenshots", "11408-scope");
const examPdf = fs.readdirSync(dir).filter(f => f.startsWith("regression-exam-11408") && f.endsWith(".pdf")).map(f => path.join(dir, f))[0];
const coursePdf = fs.readdirSync(dir).filter(f => f.startsWith("regression-course-learning") && f.endsWith(".pdf")).map(f => path.join(dir, f))[0];
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const upLog = [];
page.on("response", async (res) => { if (res.url().includes("/api/materials/upload")) { try { const j = await res.json(); upLog.push({ status: res.status(), id: j?.material_id, course_id: j?.material?.course_id, subject_key: j?.material?.subject_key, fn: j?.material?.file_name, detail: j?.detail }); } catch {} } });

async function switchToExam() {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3500);
  }
}

// ===== EXAM upload =====
await switchToExam();
await page.locator(".eh-subject-tile", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
await page.locator("input[type=file]").first().setInputFiles(examPdf).catch((e) => console.log("exam upload err", e.message));
await page.waitForTimeout(4000);

// ===== course-learning upload =====
await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3000);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3500);
}
await page.locator(".clh-course-main", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
await page.locator(".csd-nav-item", { hasText: "资料库" }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3000);
await page.locator("input[type=file]").first().setInputFiles(coursePdf).catch((e) => console.log("course upload err", e.message));
await page.waitForTimeout(4000);

console.log("===== UPLOAD LOG =====");
for (const l of upLog) console.log(JSON.stringify(l));
await browser.close();
