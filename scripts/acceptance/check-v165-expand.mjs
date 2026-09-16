import { chromium } from "playwright";
const WEB = "http://127.0.0.1:5173";
const USER = `mobile_v165_exp_${Date.now()}`;
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const api = ctx.request;
await api.post("http://127.0.0.1:8000/register", { data: { username: USER, password: "x12345" } });
const page = await ctx.newPage();
await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded" });
await page.evaluate((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify({ username: u, nickname: "V165", onboarding_completed: true })), USER);
await page.goto(`${WEB}/m/exam11408/computer_organization/chapters`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(2200);
// expand first two levels
const toggles = page.locator(".v16-tree-toggle");
const n = await toggles.count();
for (let i = 0; i < Math.min(n, 3); i++) { await toggles.nth(i).click().catch(() => {}); await page.waitForTimeout(200); }
await page.waitForTimeout(600);
const info = await page.evaluate(() => ({
  dots: document.querySelectorAll(".v16-tree-dot").length,
  badges: document.querySelectorAll(".v16-status-badge").length,
  toggles: document.querySelectorAll(".v16-tree-toggle").length,
  childrenLines: document.querySelectorAll(".v16-tree-children").length,
  sampleLeaf: [...document.querySelectorAll(".v16-tree-row.is-leaf .v16-tree-select")].slice(0,4).map(x => x.textContent.trim()),
}));
console.log(JSON.stringify(info, null, 2));
await page.screenshot({ path: "verification-results/mobile-v165/02-knowledge-expanded.png" }).catch(() => {});
await browser.close();
