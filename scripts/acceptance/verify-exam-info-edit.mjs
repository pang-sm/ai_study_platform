import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
await page.locator("[data-tour='exam-profile']").first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3500);

// Enter edit mode
await page.getByText("编辑资料", { exact: false }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(1500);
let t = await body();
console.log("edit mode — has 暂不确定:", t.includes("暂不确定"), "| select count:", await page.locator("select.ep-info-input").count(), "| date input:", await page.locator("input[type=date].ep-info-input").count());

// Change stage to 强化阶段
const stageSelect = page.locator("select.ep-info-input").nth(2);
await stageSelect.selectOption("强化阶段").catch((e) => console.log("stage select err", e.message));
// Change daily to 4 - 6 小时
const dailySelect = page.locator("select.ep-info-input").nth(3);
await dailySelect.selectOption("4 - 6 小时").catch((e) => console.log("daily select err", e.message));
await page.waitForTimeout(500);

// Save
await page.getByText("保存资料", { exact: false }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3000);
t = await body();
console.log("after save — has 强化阶段:", t.includes("强化阶段"), "| has 4 - 6 小时:", t.includes("4 - 6 小时"));

// Revert back to original values
await page.getByText("编辑资料", { exact: false }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(1500);
await page.locator("select.ep-info-input").nth(2).selectOption("冲刺阶段").catch(() => {});
await page.locator("select.ep-info-input").nth(3).selectOption("6 - 8 小时").catch(() => {});
await page.waitForTimeout(500);
await page.getByText("保存资料", { exact: false }).first().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3000);
t = await body();
console.log("after revert — has 冲刺阶段:", t.includes("冲刺阶段"), "| has 6 - 8 小时:", t.includes("6 - 8 小时"));
await browser.close();
