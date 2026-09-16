import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

const tasks = [
  { subject_key: "operating_system", title: "测试·OS-3天后", due_date: "2026-08-30" },
  { subject_key: "computer_network", title: "测试·计网-5天后", due_date: "2026-09-01" },
  { subject_key: "data_structure", title: "测试·DS-今天", due_date: "2026-08-27" },
  { subject_key: "computer_organization", title: "测试·计组-明天", due_date: "2026-08-28" },
];
const created = [];
for (const t of tasks) {
  const r = await ctx.request.post(`${BASE}/api/exam/11408/subjects/${t.subject_key}/study-plan/tasks`, {
    data: { username: "奶12", subject_key: t.subject_key, title: t.title, knowledge_point_name: "测试知识点", scope_type: "single", task_type: "knowledge", due_date: t.due_date, note: "" },
  }).catch(async e => { console.log("POST err", e.message); return null; });
  if (r) { const j = await r.json().catch(() => ({})); if (j?.task?.id) created.push(j.task); }
}
console.log("created:", created.map(c => `${c.title}(${c.id},due=${c.due_date})`));

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2200);
await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(4000);
const planTitles = await page.evaluate(() => {
  const card = Array.from(document.querySelectorAll(".eh-card")).find(c => c.innerText.includes("学习计划"));
  return card ? Array.from(card.querySelectorAll(".eh-task-card-title")).map(t => t.innerText.trim()) : [];
});
console.log("PLAN TITLES (order):", JSON.stringify(planTitles));

for (const c of created) {
  await ctx.request.delete(`${BASE}/api/exam/11408/subjects/${c.subject_key}/study-plan/tasks/${c.id}`, { data: { username: "奶12" } }).catch(() => {});
}
console.log("cleanup done");
await browser.close();
