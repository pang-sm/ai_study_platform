import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT_DIR = path.join(PROJECT_ROOT, "verification-screenshots", "11408-home-fix");
fs.mkdirSync(SHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });

async function newPage(viewport) {
  const ctx = await browser.newContext({ storageState: AUTH, viewport });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  return { ctx, page, errors };
}
const shot = (page, name) => page.screenshot({ path: path.join(SHOT_DIR, name + ".png") }).catch(() => {});
const text = (page) => page.evaluate(() => document.body.innerText);

async function switchToExam(page) {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3200);
  // if still on programming home, switch via profile
  if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2200);
    await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3800);
  }
}

// ===== Main page checks (1920x1080) =====
console.log("===== EXAM HOME (1920x1080) =====");
{
  const { ctx, page, errors } = await newPage({ width: 1920, height: 1080 });
  await switchToExam(page);
  console.log("URL:", page.url());
  const t = await text(page);
  console.log("--- home text (first 1600) ---");
  console.log(t.slice(0, 1600));
  // avatar check
  const avatarIsImg = await page.locator(".eh-user-avatar--img").count();
  console.log("avatar img count:", avatarIsImg, "(>0 means real avatar shown)");
  // package label
  console.log("has 全程考包:", t.includes("全程考包"), "| has 免费模式:", t.includes("免费模式"));
  // progress: look for a % value
  const pctMatch = t.match(/(\d{1,3})%/);
  console.log("progress percent found:", pctMatch ? pctMatch[0] : null);
  await shot(page, "1-home");
  await ctx.close();
}

// ===== 我的套餐 (ExamProfile) =====
console.log("\n===== 我的套餐 (ExamProfile) =====");
{
  const { ctx, page } = await newPage({ width: 1440, height: 900 });
  await switchToExam(page);
  await page.getByText("个人资料", { exact: false }).first().click({ timeout: 10000 }).catch(async () => {
    await page.locator("[data-tour='exam-profile']").first().click({ timeout: 10000 }).catch(() => {});
  });
  await page.waitForTimeout(3000);
  const t = await text(page);
  console.log("profile URL:", page.url());
  console.log("has 全程考包:", t.includes("全程考包"), "| has 免费模式:", t.includes("免费模式"));
  console.log("学习计划已解锁:", t.includes("学习计划") && t.includes("已解锁"));
  await shot(page, "2-profile");
  await ctx.close();
}

// ===== 套餐选择页 (MembershipPage) =====
console.log("\n===== 套餐选择页 (Membership) =====");
{
  const { ctx, page } = await newPage({ width: 1440, height: 900 });
  await switchToExam(page);
  await page.getByText("个人资料", { exact: false }).first().click({ timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(2500);
  await page.getByText("查看套餐详情", { exact: false }).first().click({ timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(3500);
  const t = await text(page);
  console.log("membership URL:", page.url());
  console.log("has 全程考包:", t.includes("全程考包"), "| has 当前方案:", t.includes("当前方案"));
  await shot(page, "3-membership");
  await ctx.close();
}

// ===== 资料库 最近上传时间 =====
console.log("\n===== 资料库 最近上传时间 =====");
{
  const { ctx, page } = await newPage({ width: 1440, height: 900 });
  await switchToExam(page);
  await page.locator(".eh-subject-tile", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2800);
  await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3200);
  const t = await text(page);
  console.log("materials URL:", page.url());
  const m = t.match(/最近上传时间\s*([\d\/\s:]+)/);
  console.log("最近上传时间 value:", m ? m[1].trim() : "NOT FOUND");
  await shot(page, "4-materials");
  await ctx.close();
}

// ===== 三种分辨率滚动 =====
console.log("\n===== SCROLL (3 resolutions) =====");
for (const vp of [{ w: 1920, h: 1080 }, { w: 1536, h: 864 }, { w: 1366, h: 768 }]) {
  const { ctx, page } = await newPage({ width: vp.w, height: vp.h });
  await switchToExam(page);
  const scrollH = await page.evaluate(() => document.querySelector(".exam-home-page")?.scrollHeight ?? 0);
  const clientH = await page.evaluate(() => document.querySelector(".exam-home-page")?.clientHeight ?? 0);
  // try scroll to bottom
  await page.evaluate(() => { const el = document.querySelector(".exam-home-page"); if (el) el.scrollTop = el.scrollHeight; });
  await page.waitForTimeout(800);
  const scrolled = await page.evaluate(() => { const el = document.querySelector(".exam-home-page"); return el ? el.scrollTop : 0; });
  const bodyHScroll = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  console.log(`${vp.w}x${vp.h}: scrollHeight=${scrollH} clientHeight=${clientH} scrollTopAfter=${scrolled} bodyHScroll=${bodyHScroll}`);
  await shot(page, `scroll-${vp.w}x${vp.h}`);
  await ctx.close();
}

await browser.close();
console.log("\nDONE");
