import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT_DIR = path.join(PROJECT_ROOT, "verification-screenshots", "11408-round3");
fs.mkdirSync(SHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const shot = (n) => page.screenshot({ path: path.join(SHOT_DIR, n + ".png") }).catch(() => {});
const body = () => page.evaluate(() => document.body.innerText);

async function switchToExam() {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3200);
  if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2200);
    await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3800);
  }
}
async function enterSubject(subj, panel) {
  await page.locator(".eh-subject-tile", { hasText: subj }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2800);
}

// 1) 学科首页 精简 + 头像
console.log("===== 1. 学科首页（计组）=====");
await switchToExam();
await enterSubject("计算机组成原理");
await page.waitForTimeout(1200);
let t = await body();
console.log("URL:", page.url());
console.log("has '课程学习 / 当前科目':", t.includes("课程学习 / 当前科目"));
console.log("has '开始今天的':", t.includes("开始今天的"));
console.log("has '高频得分区':", t.includes("高频得分区"));
console.log("avatar img count:", await page.locator(".exam-subject-profile-avatar").count(), "isImg:", await page.locator(".exam-subject-profile-avatar").first().evaluate(el => el.tagName).catch(() => "?"));
console.log("has 课程概览:", t.includes("课程概览"), "| has 今日学习计划:", t.includes("今日学习计划"), "| has 额度剩余:", t.includes("额度剩余"));
await shot("1-coa-home");

// 2) 资料库 标题删除
console.log("\n===== 2. 资料库（计组）=====");
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
t = await body();
console.log("URL:", page.url());
console.log("has '资料库 · 计算机组成原理':", t.includes("资料库 · 计算机组成原理"));
console.log("has '当前课程：11408':", t.includes("当前课程：11408"));
console.log("has 上传课程资料:", t.includes("上传课程资料"), "| has 重建索引:", t.includes("重建索引"), "| has 资料总数:", t.includes("资料总数"));
await shot("2-coa-materials");

// 3) 章节练习
console.log("\n===== 3. 章节练习（数据结构）=====");
await page.getByText("返回主页", { exact: true }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(2500);
await enterSubject("数据结构");
await page.getByRole("button", { name: "练习中心" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
t = await body();
console.log("练习中心 URL:", page.url());
const cardText = await page.evaluate(() => {
  const card = Array.from(document.querySelectorAll(".practice-type-card, [class*=practice-type]")).find(c => c.innerText.includes("章节练习"));
  return card ? card.innerText.replace(/\s+/g, " ").slice(0, 120) : "NOT FOUND";
});
console.log("章节练习卡片:", cardText);
console.log("has 题目待录入:", t.includes("题目待录入"));
await shot("3-ds-practice");
// enter chapter practice
await page.getByText("章节练习", { exact: true }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3000);
t = await body();
console.log("章节练习页 URL:", page.url());
console.log("has 总题数:", t.includes("总题数"), "| has 开始练习:", t.includes("开始练习"));
await shot("4-ds-chapter");

// 4) 个人资料 备考信息 + 注册时间
console.log("\n===== 4. 个人资料 =====");
await page.getByText("个人资料", { exact: false }).first().click({ timeout: 10000 }).catch(async () => {
  await page.locator(".exam-subject-profile").first().click({ timeout: 10000 }).catch(() => {});
});
await page.waitForTimeout(3000);
t = await body();
console.log("个人资料 URL:", page.url());
const regMatch = t.match(/注册时间[^\d]*(\d{4}-\d{2}-\d{2})/);
console.log("注册时间显示:", regMatch ? regMatch[1] : "NOT FOUND");
console.log("注册时间含完整时间戳:", /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(t));
console.log("has 考试时间:", t.includes("考试时间"), "| has 当前备考阶段:", t.includes("当前备考阶段"), "| has 每天学习时间:", t.includes("每天学习时间"));
await shot("5-profile");

console.log("\nDONE");
await browser.close();
