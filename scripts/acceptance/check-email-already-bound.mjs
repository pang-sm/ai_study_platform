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
const j = await me.json().catch(() => ({}));
const email = j?.user?.email;
console.log("email:", JSON.stringify(email), "verified:", j?.user?.email_verified);
if (email) {
  const r = await api.post(`${BASE}/api/me/email/send-code?username=${encodeURIComponent("奶12")}`, { data: { email } });
  console.log("send-code (already bound):", r.status(), JSON.stringify(await r.json().catch(() => ({}))));
}
await browser.close();
