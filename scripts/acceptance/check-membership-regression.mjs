import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH });
const api = ctx.request;

const me = await api.post(`${BASE}/api/me`, { data: { username: "奶12" } });
console.log("=== /api/me status:", me.status());
if (me.status() === 200) {
  const j = await me.json();
  console.log("service_plans:", JSON.stringify(j?.user?.service_plans, null, 2));
  console.log("active_track_type:", j?.user?.active_track_type);
  console.log("tracks:", JSON.stringify((j?.user?.tracks||[]).map(t=>({type:t.track_type, plan:t.plan, pkg:t.package_type})), null, 2));
} else {
  console.log("me body:", (await me.text()).slice(0, 500));
}

for (const sk of ["exam_11408", "course_learning", "programming"]) {
  const r = await api.get(`${BASE}/api/membership/catalog?service_key=${sk}`);
  console.log(`=== catalog ${sk} status:`, r.status(), "body:", (await r.text()).slice(0, 300));
}
await browser.close();
