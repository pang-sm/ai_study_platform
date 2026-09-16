import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const body = () => page.evaluate(() => document.body.innerText);
const api = ctx.request;

// API: email already-bound check
let r = await api.post(`${BASE}/api/me`, { data: { username: "奶12" } });
let j = await r.json().catch(() => ({}));
const email = j?.user?.email || "";
const verified = j?.user?.email_verified;
console.log("奶12 email:", JSON.stringify(email), "verified:", verified);

if (verified) {
  r = await api.post(`${BASE}/api/me/email/send-code?username=${encodeURIComponent("奶12")}`, { data: { email } });
  console.log("send-code (already bound):", r.status(), JSON.stringify(await r.json().catch(() => ({}))));
}

// Browser: profile account security
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3000);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3500);
}
await page.locator("[data-tour='exam-profile']").first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3500);
let t = await body();
console.log("=== 账号安全 ===");
console.log("has '绑定手机号':", t.includes("绑定手机号"));
console.log("has '手机号':", t.includes("手机号"));
console.log("has '绑定邮箱':", t.includes("绑定邮箱"));
console.log("has '已验证':", t.includes("已验证"));
console.log("has '更换邮箱':", t.includes("更换邮箱"));
console.log("has '修改':", t.includes("修改") && t.includes("密码") ? "仅密码" : t.includes("修改"));
await page.screenshot({ path: path.join(PROJECT_ROOT, "verification-screenshots", "account-security.png") }).catch(() => {});
await browser.close();
