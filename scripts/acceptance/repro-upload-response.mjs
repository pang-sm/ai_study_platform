import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const TEST_FILE = "C:/Users/26477/Desktop/课程文件/大二上/计组/coa26_书面作业01.pdf";

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

page.on("response", async (res) => {
  if (res.url().includes("/api/materials/upload")) {
    const txt = await res.text().catch(() => "(no body)");
    console.log("UPLOAD RESPONSE status=", res.status(), "body=", txt.slice(0, 800));
  }
});

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
await page.locator(".eh-subject-tile", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2800);
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3500);
console.log("URL:", page.url());
// Capture console errors too
page.on("console", (m) => { if (m.type() === "error") console.log("CONSOLE ERROR:", m.text().slice(0, 300)); });
page.on("pageerror", (e) => console.log("PAGE ERROR:", e.message.slice(0, 300)));

await page.locator("input[type=file]").first().setInputFiles(TEST_FILE).catch((e) => console.log("setInputFiles err", e.message));
await page.waitForTimeout(6000);
const tip = await page.evaluate(() => { const el = document.querySelector(".cmp-upload-notice, [class*=tip], [class*=message]"); return el ? el.innerText.slice(0,200) : ""; });
console.log("TIP/notice:", tip);
await browser.close();
