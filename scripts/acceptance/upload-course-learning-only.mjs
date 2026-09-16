import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const dir = path.join(PROJECT_ROOT, "verification-screenshots", "11408-scope");
const coursePdf = fs.readdirSync(dir).filter(f => f.startsWith("regression-course-learning") && f.endsWith(".pdf")).map(f => path.join(dir, f))[0];
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const upLog = [];
page.on("response", async (res) => { if (res.url().includes("/api/materials/upload")) { try { const j = await res.json(); upLog.push({ status: res.status(), id: j?.material_id, course_id: j?.material?.course_id, subject_key: j?.material?.subject_key, fn: j?.material?.file_name, detail: j?.detail }); } catch {} } });

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
console.log("STEP0 landing URL:", page.url());
// Switch to course-learning via profile
await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch((e) => console.log("profile err", e.message));
await page.waitForTimeout(2200);
console.log("STEP1 profile URL:", page.url());
await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch((e) => console.log("switch err", e.message));
await page.waitForTimeout(3800);
console.log("STEP2 after switch URL:", page.url());
// click course
await page.locator(".clh-course-main", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch((e) => console.log("course err", e.message));
await page.waitForTimeout(3000);
console.log("STEP3 course URL:", page.url());
// 资料库
await page.locator(".csd-nav-item", { hasText: "资料库" }).first().click({ timeout: 10000 }).catch((e) => console.log("mat err", e.message));
await page.waitForTimeout(3000);
console.log("STEP4 materials URL:", page.url());
// upload
await page.locator("input[type=file]").first().setInputFiles(coursePdf).catch((e) => console.log("upload err", e.message));
await page.waitForTimeout(4000);
console.log("STEP5 after upload URL:", page.url());
console.log("===== UPLOAD LOG =====");
for (const l of upLog) console.log(JSON.stringify(l));
await browser.close();
