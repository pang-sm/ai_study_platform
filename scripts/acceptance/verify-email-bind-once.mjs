import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT = path.join(PROJECT_ROOT, "verification-screenshots", "email-bind-once");
fs.mkdirSync(SHOT, { recursive: true });
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);
const has = async (s) => (await body()).includes(s);

async function goCourseProfile() {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3500);
  }
  await page.locator(".clh-user-card").first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3500);
}

await goCourseProfile();
console.log("=== 课程学习 个人资料 账号安全 ===");
console.log("更换邮箱:", await has("更换邮箱"), "| 修改邮箱:", await has("修改邮箱"), "| 解绑邮箱:", await has("解绑邮箱"));
console.log("绑定邮箱按钮:", await has("绑定邮箱"));
// click 绑定邮箱
await page.getByRole("button", { name: "绑定邮箱" }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(800);
let t = await body();
console.log("=== 弹窗 ===");
console.log("标题绑定邮箱:", t.includes("绑定邮箱"), "| 更换邮箱:", t.includes("更换邮箱"), "| 新邮箱:", t.includes("新邮箱"), "| 当前邮箱:", t.includes("当前邮箱"));
console.log("一次绑定提醒:", t.includes("邮箱仅可绑定一次"));
await page.screenshot({ path: path.join(SHOT, "email-bind-modal.png") }).catch(() => {});

// click 确认绑定 (no email entered -> should show validation error, not final confirm)
await page.getByRole("button", { name: "确认绑定" }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(500);
t = await body();
console.log("空邮箱提示(请输入有效):", t.includes("请输入有效") || t.includes("请输入 6 位"));
await browser.close();
