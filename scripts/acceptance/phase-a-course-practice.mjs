import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT = path.join(PROJECT_ROOT, "verification-screenshots", "phase-a");
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
// switch to course-learning via profile
await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch((e) => console.log("profile err", e.message));
await page.waitForTimeout(2200);
await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch((e) => console.log("switch err", e.message));
await page.waitForTimeout(3800);
console.log("course home URL:", page.url());
// click 计算机网络 course
await page.locator(".clh-course-main", { hasText: "计算机网络" }).first().click({ timeout: 15000 }).catch((e) => console.log("course err", e.message));
await page.waitForTimeout(3000);
console.log("course dashboard URL:", page.url());
// click 章节练习 nav
await page.locator(".csd-nav-item", { hasText: "章节练习" }).first().click({ timeout: 10000 }).catch((e) => console.log("practice err", e.message));
await page.waitForTimeout(3000);
let t = await body();
console.log("practice URL:", page.url());
console.log("has 'AI WORKBOOK':", t.includes("AI WORKBOOK"), "| has '章节练习 ·':", t.includes("章节练习 ·"), "| has '当前范围':", t.includes("当前范围"));
await page.screenshot({ path: path.join(SHOT, "course-chapter-practice.png") }).catch(() => {});
await browser.close();
