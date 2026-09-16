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
  const tbodies = document.querySelectorAll("tbody");
  const tables = document.querySelectorAll("table");
  return {
    tableCount: tables.length,
    tbodyCount: tbodies.length,
    tbodyHTML: Array.from(tbodies).map(t => t.innerHTML.slice(0, 300)),
    cmpRows: document.querySelectorAll(".cmp-table tr, table tr").length,
    cmpFileCells: document.querySelectorAll(".cmp-file-cell").length,
  };
});
console.log(JSON.stringify(info, null, 2));
await browser.close();
