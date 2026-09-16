import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(SCRIPT_DIR, "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const SHOT_DIR = path.join(PROJECT_ROOT, "verification-screenshots", "11408-scope");
fs.mkdirSync(SHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text().slice(0, 200)); });

const shot = async (name) => {
  await page.screenshot({ path: path.join(SHOT_DIR, name + ".png"), fullPage: false }).catch(() => {});
  console.log(`[shot] ${name}.png  URL=${page.url()}`);
};
const dump = async (label, n = 1400) => {
  const t = await page.evaluate(() => document.body.innerText);
  console.log(`\n----- ${label} (URL=${page.url()}) -----`);
  console.log(t.slice(0, n));
};

async function goExamSubject(subj) {
  await page.locator(".eh-subject-tile", { hasText: subj }).first().click({ timeout: 15000 }).catch((e) => console.log("tile click err", e.message));
  await page.waitForTimeout(3000);
}

console.log("STEP 1: production home (saved login 奶12)");
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3500);
await shot("1-home");

console.log("\nSTEP 2: profile -> 切换到 11408");
await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);
await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch((e) => console.log("switch err", e.message));
await page.waitForTimeout(4000);
await shot("2-exam-home");
await dump("exam-home (11408 首页)", 500);

console.log("\nSTEP 3: 计算机组成原理");
await goExamSubject("计算机组成原理");
await shot("3-coa-home");
await dump("coa-home (计组主页)", 500);

console.log("\nSTEP 4: 资料库");
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch((e) => console.log("materials err", e.message));
await page.waitForTimeout(3500);
await shot("4-materials");
await dump("materials (资料库)", 1600);

console.log("\nSTEP 5: F5");
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
await shot("5-f5");
await dump("f5", 800);

console.log("\nSTEP 6: Ctrl+F5");
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
await shot("6-ctrlf5");
await dump("ctrlf5", 800);

console.log("\nSTEP 7: cross-subject isolation (数据结构 / 操作系统 / 计算机网络)");
const results = {};
for (const subj of ["数据结构", "操作系统", "计算机网络"]) {
  try {
    await page.goto(BASE + "/", { waitUntil: "domcontentloaded" }).catch(() => {});
    await page.waitForTimeout(2500);
    // land on exam home directly (exam track is active now)
    await page.locator(".eh-subject-tile", { hasText: subj }).first().click({ timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(2500);
    await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(2500);
    const u = page.url();
    const txt = await page.evaluate(() => document.body.innerText);
    results[subj] = { url: u, hasCOA: txt.includes("coa26_第0讲"), hasChapter1: txt.includes("chapter1_introduction") };
    console.log(`ISOLATION ${subj}: url=${u} hasCOA=${results[subj].hasCOA} hasChapter1=${results[subj].hasChapter1}`);
    await shot(`iso-${subj}`);
  } catch (e) {
    results[subj] = { error: e.message };
    console.log(`ISOLATION ${subj}: ERROR ${e.message}`);
  }
}

console.log("\n===== SUMMARY =====");
console.log("JS errors:", JSON.stringify(errors.slice(0, 10), null, 2));
console.log("Isolation:", JSON.stringify(results, null, 2));
await browser.close();
