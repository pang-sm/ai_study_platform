import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3000);
// unscoped list
const all = await page.evaluate(async () => {
  const r = await fetch("/api/materials?username=奶12", { credentials: "include" });
  return (await r.json()).materials || [];
});
console.log("=== 奶12 全部资料（按 scope 分组）===");
for (const m of all) {
  console.log(`#${m.id} | course_id=${m.course_id} | subject_key=${m.subject_key} | subject=${m.subject} | ${m.original_filename}`);
}
await browser.close();
