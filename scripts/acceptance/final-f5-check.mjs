import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const files = () => page.evaluate(() => Array.from(document.querySelectorAll("tbody tr td:first-child")).map(t => t.innerText.trim()).filter(Boolean));

// course-learning 计组, direct to URL (already has session)
await page.goto(BASE + "/course-learning/computer_organization/materials", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(6000);
console.log("COURSE F5 direct-load:", page.url(), JSON.stringify(await files()));
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(3000);
console.log("COURSE after reload:", page.url(), JSON.stringify(await files()));
await browser.close();
