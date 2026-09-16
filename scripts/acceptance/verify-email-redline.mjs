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
const check = async (label) => {
  console.log(`${label}: 更换邮箱=${await has("更换邮箱")} 修改邮箱=${await has("修改邮箱")} 解绑邮箱=${await has("解绑邮箱")} 绑定邮箱按钮=${await has("绑定邮箱")} 已验证=${await has("已验证")}`);
};
await check("课程profile");
await page.screenshot({ path: path.join(SHOT, "bound-email.png") }).catch(() => {});
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
await check("F5后");
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
await check("Ctrl+F5后");
await browser.close();
