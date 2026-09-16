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
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3000);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3500);
}
await page.locator(".eh-subject-tile", { hasText: "数据结构" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
// click the first "···" button
await page.locator(".cmp-action-menu-wrap button[title='更多操作']").first().click({ timeout: 10000 }).catch((e) => console.log("menu err", e.message));
await page.waitForTimeout(800);
const menuText = await page.evaluate(() => {
  const m = document.querySelector(".cmp-action-menu");
  return m ? m.innerText.replace(/\s+/g, " ") : "NO MENU";
});
console.log("MENU:", JSON.stringify(menuText));
await page.screenshot({ path: path.join(PROJECT_ROOT, "verification-screenshots", "delete-menu.png") }).catch(() => {});
// click 删除资料
await page.locator(".cmp-action-menu button", { hasText: "删除资料" }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(800);
const modalText = await page.evaluate(() => {
  const m = document.querySelector(".cmp-delete-modal");
  return m ? m.innerText.replace(/\s+/g, " ") : "NO MODAL";
});
console.log("MODAL:", JSON.stringify(modalText));
await page.screenshot({ path: path.join(PROJECT_ROOT, "verification-screenshots", "delete-modal.png") }).catch(() => {});
await browser.close();
