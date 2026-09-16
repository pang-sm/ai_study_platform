// Phase 4B-1.4 canonical curriculum resolver — real authenticated browser.
// Reuses the Auth V2 formal user (acceptance_v2_user) via the real login UI,
// then walks /exam/11408 -> /exam/11408/operating-system -> workspace, verifies
// the resolver against the real study-plan API and captures screenshots.
import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { mkdirSync } from "node:fs";

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SHOT_DIR = path.join(PROJECT_ROOT, "reference", "PAGE", "vertical-slice-v1", "phase4b1-real-final");
const BASE = "http://localhost:5173";
const USER = "acceptance_v2_user";
const PASS = "secret123";

mkdirSync(SHOT_DIR, { recursive: true });

const studyPlanStatuses = [];
const consoleErrors = [];
let resolverErrors = [];

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => {
  consoleErrors.push(err.message);
  if (/curriculum|study-plan|knowledge point|virtual-memory/i.test(err.message)) resolverErrors.push(err.message);
});
page.on("response", (res) => {
  const u = res.url();
  if (u.includes("/study-plan") && u.includes("operating_system")) {
    studyPlanStatuses.push({ status: res.status(), url: u.replace(/^https?:\/\/[^/]+/, "") });
  }
});

async function login() {
  await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.fill("#auth-username", USER);
  await page.fill("#auth-password", PASS);
  await Promise.all([
    page.waitForURL((url) => url.pathname === "/", { timeout: 20000 }),
    page.getByRole("button", { name: "登录并进入学习" }).click(),
  ]);
}

async function gotoAndCheck(url, markers, shotName) {
  await page.goto(`${BASE}${url}`, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(800);
  const visible = [];
  for (const marker of markers) {
    const found = await page.getByText(marker, { exact: false }).first().isVisible().catch(() => false);
    visible.push({ marker, found });
  }
  await page.screenshot({ path: path.join(SHOT_DIR, shotName), fullPage: false });
  return visible;
}

const results = {};

await login();
results.loginUrl = page.url();

results.exam11408 = await gotoAndCheck(
  "/exam/11408",
  ["页框分配", "虚拟内存管理"],
  "11408_real_1440.png",
);
results.operatingSystem = await gotoAndCheck(
  "/exam/11408/operating-system",
  ["虚拟内存地址映射", "地址变换机构", "请求分页管理方式"],
  "operating_system_real_1440.png",
);
results.workspace = await gotoAndCheck(
  "/exam/11408/operating-system/workspace",
  ["虚拟内存地址映射", "页框分配"],
  "workspace_real_1440.png",
);

// Deep refresh — re-request the workspace URL directly.
const beforeReload = page.url();
await page.reload({ waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(800);
results.deepRefresh = {
  url: page.url(),
  rendered: await page.getByText("虚拟内存地址映射", { exact: false }).first().isVisible().catch(() => false),
  nextVisible: await page.getByText("页框分配", { exact: false }).first().isVisible().catch(() => false),
};

// Mobile workspace
const mctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await mctx.addCookies(await ctx.cookies());
const mpage = await mctx.newPage();
mpage.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(`[mobile] ${msg.text()}`); });
await mpage.goto(`${BASE}/exam/11408/operating-system/workspace`, { waitUntil: "networkidle", timeout: 60000 });
await mpage.waitForTimeout(800);
results.mobile = {
  rendered: await mpage.getByText("虚拟内存地址映射", { exact: false }).first().isVisible().catch(() => false),
};
await mpage.screenshot({ path: path.join(SHOT_DIR, "workspace_real_390.png"), fullPage: false });
await mctx.close();

console.log("=== LOGIN ===");
console.log("loginUrl:", results.loginUrl);
console.log("=== STUDY-PLAN (operating_system) ===");
for (const s of studyPlanStatuses) console.log(JSON.stringify(s));
console.log("=== RENDER ===");
console.log("exam11408:", JSON.stringify(results.exam11408));
console.log("operatingSystem:", JSON.stringify(results.operatingSystem));
console.log("workspace:", JSON.stringify(results.workspace));
console.log("deepRefresh:", JSON.stringify(results.deepRefresh));
console.log("mobile:", JSON.stringify(results.mobile));
console.log("=== CONSOLE ERRORS ===");
console.log(JSON.stringify(consoleErrors));
console.log("=== RESOLVER ERRORS ===");
console.log(JSON.stringify(resolverErrors));

await browser.close();
