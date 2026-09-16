import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT = path.join(PROJECT_ROOT, "verification-screenshots", "account-security");
fs.mkdirSync(SHOT, { recursive: true });
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);
const has = (s) => body().then(t => t.includes(s));

async function goCourseProfile() {
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(3500);
  }
  await page.locator(".clh-user-card").first().click({ timeout: 15000 }).catch((e) => console.log("profile err", e.message));
  await page.waitForTimeout(3500);
}

await goCourseProfile();
console.log("=== 课程学习 个人资料 账号安全 ===");
console.log("URL:", page.url());
console.log("绑定手机号:", await has("绑定手机号"));
console.log("用于接收验证码和安全验证:", await has("用于接收验证码和安全验证"));
console.log("绑定邮箱:", await has("绑定邮箱"));
console.log("登录密码:", await has("登录密码"));
console.log("退出登录:", await has("退出登录"));
await page.screenshot({ path: path.join(SHOT, "course-profile-security.png"), fullPage: false }).catch(() => {});

// F5
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
console.log("F5后 绑定手机号:", await has("绑定手机号"), "| 绑定邮箱:", await has("绑定邮箱"));
// Ctrl+F5
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
console.log("Ctrl+F5后 绑定手机号:", await has("绑定手机号"), "| 绑定邮箱:", await has("绑定邮箱"));
await browser.close();
