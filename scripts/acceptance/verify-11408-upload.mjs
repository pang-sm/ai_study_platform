import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT_DIR = path.join(PROJECT_ROOT, "verification-screenshots", "11408-scope");

const pdfs = fs.readdirSync(SHOT_DIR).filter((f) => f.startsWith("scope-11408-coa-final-") && f.endsWith(".pdf"));
if (!pdfs.length) { console.log("NO PDF FOUND"); process.exit(1); }
const PDF = path.join(SHOT_DIR, pdfs[0]);
const FILENAME = pdfs[0];
console.log("Uploading:", FILENAME);

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));

// boot to 11408 exam home
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3500);
await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);
await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(4000);

// go to 计算机组成原理 -> 资料库
await page.locator(".eh-subject-tile", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2800);
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3000);
console.log("Before upload URL:", page.url());

// upload the file
await page.locator("input[type=file]").first().setInputFiles(PDF).catch((e) => console.log("setInputFiles err", e.message));
console.log("Upload triggered");

// wait for the new filename to appear in the list (without reload)
let appeared = false;
for (let i = 0; i < 20; i++) {
  await page.waitForTimeout(1500);
  const txt = await page.evaluate(() => document.body.innerText);
  if (txt.includes(FILENAME)) { appeared = true; break; }
}
console.log("appearedWithoutReload:", appeared);
await page.waitForTimeout(2000);
const finalTxt = await page.evaluate(() => document.body.innerText);
console.log("has coa26:", finalTxt.includes("coa26_第0讲.pdf"));
console.log("has new file:", finalTxt.includes(FILENAME));
await page.screenshot({ path: path.join(SHOT_DIR, "upload-result.png") }).catch(() => {});
console.log("After upload URL:", page.url());
console.log("JS errors:", JSON.stringify(errors.slice(0, 5)));
await browser.close();
