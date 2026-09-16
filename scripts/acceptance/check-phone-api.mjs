import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH });
const api = ctx.request;

// invalid phone
let r = await api.post(`${BASE}/api/me/phone/send-code`, { data: { phone: "123" } });
console.log("invalid phone:", r.status(), JSON.stringify(await r.json()));

// valid phone (SMS not configured → 503)
r = await api.post(`${BASE}/api/me/phone/send-code`, { data: { phone: "13812345678" } });
console.log("valid phone (no SMS cfg):", r.status(), JSON.stringify(await r.json()));

// verify without code
r = await api.post(`${BASE}/api/me/phone/verify`, { data: { phone: "13812345678", code: "123456" } });
console.log("verify (no code sent):", r.status(), JSON.stringify(await r.json()));

await browser.close();
