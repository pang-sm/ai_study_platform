import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH });
for (const subj of ["data_structure", "computer_organization", "operating_system", "computer_network"]) {
  const r = await ctx.request.get(`${BASE}/api/exam/11408/${subj}/chapter-practice/questions?username=${encodeURIComponent("奶12")}`);
  const j = await r.json().catch(() => ({}));
  console.log(subj, "status", r.status(), "total", j.total, "items", (j.items || []).length);
}
await browser.close();
