import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await page.goto(BASE + "/programming/python_programming/materials", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(6000);
const info = await page.evaluate(() => {
  const rows = document.querySelectorAll("tr");
  const tds = document.querySelectorAll("td");
  const fileCell = document.querySelectorAll(".cmp-file-cell span");
  return {
    bodyLen: document.body.innerText.length,
    trCount: rows.length,
    tdCount: tds.length,
    fileCellCount: fileCell.length,
    fileCellTexts: Array.from(fileCell).map(e => e.textContent).slice(0, 5),
    hasEmptyState: document.body.innerText.includes("当前科目还没有资料"),
    hasTable: document.body.innerText.includes("上传时间"),
  };
});
console.log(JSON.stringify(info, null, 2));
await browser.close();
