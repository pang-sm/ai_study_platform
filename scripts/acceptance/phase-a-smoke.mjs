import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT = path.join(PROJECT_ROOT, "verification-screenshots", "phase-a");
fs.mkdirSync(SHOT, { recursive: true });
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);
const shot = (n) => page.screenshot({ path: path.join(SHOT, n + ".png") }).catch(() => {});

async function switchExam() {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3200);
  if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3500);
  }
}

// 11408 数据结构
await switchExam();
await page.locator(".eh-subject-tile", { hasText: "数据结构" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);

// 知识脉络
await page.locator(".exam-subject-nav-item", { hasText: "知识脉络" }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3000);
let t = await body();
console.log("=== 11408 知识脉络 ===");
console.log("URL:", page.url());
console.log("has '知识脉络 · 数据结构':", t.includes("知识脉络 · 数据结构"));
console.log("has '当前课程：':", t.includes("当前课程："));
console.log("has 知识点总数:", t.includes("知识点总数"), "| has 搜索:", t.includes("搜索"));
await shot("11408-knowledge");

// 学习计划
await page.locator(".exam-subject-nav-item", { hasText: "学习计划" }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3000);
t = await body();
console.log("=== 11408 学习计划 ===");
console.log("has '学习计划 / 知识点联动':", t.includes("知识点联动"));
console.log("has '阶段学习任务':", t.includes("阶段学习任务"), "| has '新建任务':", t.includes("新建任务"));
await shot("11408-plan");

// course-learning 章节练习
await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3000);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3500);
}
await page.locator(".clh-course-main", { hasText: "计算机网络" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2800);
await page.locator(".csd-nav-item", { hasText: "章节练习" }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3000);
t = await body();
console.log("=== course-learning 章节练习 ===");
console.log("URL:", page.url());
console.log("has 'AI WORKBOOK':", t.includes("AI WORKBOOK"));
console.log("has 'AI 题册':", t.includes("AI 题册"));
console.log("has '章节练习 · 计算机网络':", t.includes("章节练习 · 计算机网络"));
console.log("has '当前范围':", t.includes("当前范围"));
console.log("has '生成的题目会长期保留':", t.includes("生成的题目会长期保留"));
await shot("course-chapter-practice");

await browser.close();
console.log("DONE");
