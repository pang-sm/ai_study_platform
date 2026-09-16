import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH });
const r = await ctx.request.post(`${BASE}/api/exam/11408/subjects/data_structure/study-plan/tasks`, {
  data: { username: "奶12", title: "测试A", knowledge_point_name: "测试知识点", scope_type: "single", task_type: "knowledge", due_date: "2026-08-27", note: "" },
});
console.log("status:", r.status());
console.log("body:", (await r.text()).slice(0, 500));
await browser.close();
