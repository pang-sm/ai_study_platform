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

const shot = async (name) => { await page.screenshot({ path: path.join(SHOT_DIR, name + ".png") }).catch(() => {}); };

async function toExamHome() {
  // If already on a subject dashboard, click 返回主页
  const back = page.getByText("返回主页", { exact: true }).first();
  if (await back.isVisible().catch(() => false)) {
    await back.click({ timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(2500);
    return;
  }
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" }).catch(() => {});
  await page.waitForTimeout(3000);
}

async function openSubjectMaterials(subj) {
  await page.locator(".eh-subject-tile", { hasText: subj }).first().click({ timeout: 12000 }).catch(() => {});
  await page.waitForTimeout(2800);
  await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 12000 }).catch(() => {});
  await page.waitForTimeout(3000);
}

console.log("Boot to 11408 exam home");
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3500);
// Switch from programming track to 11408 via profile
await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2500);
await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(4000);

const results = {};
for (const subj of ["数据结构", "操作系统", "计算机网络"]) {
  try {
    await toExamHome();
    await openSubjectMaterials(subj);
    const u = page.url();
    const txt = await page.evaluate(() => document.body.innerText);
    const files = ["coa26_第0讲.pdf", "chapter1_introduction.pdf", "论文主要内容 (1).docx", "01-引言+命题逻辑.pdf", "ch03.pptx"];
    results[subj] = { url: u, files: {} };
    for (const f of files) results[subj].files[f] = txt.includes(f);
    console.log(`ISOLATION ${subj}:\n  url=${u}\n  ${JSON.stringify(results[subj].files)}`);
    await shot(`iso2-${subj}`);
  } catch (e) {
    results[subj] = { error: e.message };
    console.log(`ISOLATION ${subj}: ERROR ${e.message}`);
  }
}

// Also verify 11408 计组 still shows ONLY coa26 (not chapter1 or ch03)
console.log("\n--- 11408 计算机组成原理 (should have ONLY coa26) ---");
try {
  await toExamHome();
  await openSubjectMaterials("计算机组成原理");
  const txt = await page.evaluate(() => document.body.innerText);
  console.log("计组 materials has coa26:", txt.includes("coa26_第0讲.pdf"), "| has chapter1:", txt.includes("chapter1_introduction.pdf"), "| has ch03:", txt.includes("ch03.pptx"));
  await shot("iso2-计组-confirm");
} catch (e) { console.log("计组 confirm ERROR", e.message); }

console.log("\n===== DONE =====");
console.log(JSON.stringify(results, null, 2));
await browser.close();
