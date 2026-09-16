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
const py = await page.evaluate(async () => {
  const r = await fetch("/api/materials?username=奶12&course_id=python_programming&track=programming", { credentials: "include" });
  return (await r.json()).materials || [];
});
console.log("=== python programming materials ===");
for (const m of py) {
  console.log(JSON.stringify({ id: m.id, fn: m.original_filename, course_id: m.course_id, subject_key: m.subject_key, parse_status: m.parse_status, file_type: m.file_type, source_type: m.source_type, chunk_count: m.chunk_count, visibility: m.visibility }));
}
await browser.close();
