import { chromium } from "playwright";
const BASE = "https://101.32.190.42";
const COOKIE = "nILnBCF5uCOPPOZpGYXWCmHC1WaBM4fYSyfeh5t41NpDql1XoUgsamDwaCySpwpN";
const USER = { username: "奶12", nickname: "奶12", onboarding_completed: true, needs_onboarding: false };

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
await ctx.addCookies([{ name: "ai_session", value: COOKIE, domain: "101.32.190.42", path: "/", httpOnly: true, secure: true, sameSite: "Lax" }]);
await ctx.addInitScript((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify(u)), USER);
const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") console.log("  [console." + m.type() + "]", m.text().slice(0, 200)); });
page.on("pageerror", (e) => console.log("  [pageerror]", e.message.slice(0, 300)));
page.on("requestfailed", (r) => console.log("  [reqfailed]", r.url().slice(0, 120), r.failure()?.errorText));
page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) console.log("  [api " + r.status() + "]", r.url().slice(0, 140)); });

for (const route of ["/m/exam11408/data_structure/chapters", "/m/exam11408/computer_organization/chapters"]) {
  console.log("\n===== " + route + " =====");
  await page.goto(BASE + route, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(4000);
  const info = await page.evaluate(() => {
    const tree = document.querySelectorAll(".v16-tree-node").length;
    const loading = [...document.querySelectorAll(".inline-state")].map((e) => e.textContent.trim());
    const error = [...document.querySelectorAll(".inline-error")].map((e) => e.textContent.trim());
    const empty = [...document.querySelectorAll(".empty-course")].map((e) => e.textContent.trim());
    const heading = document.querySelector(".v16-knowledge-head h1")?.textContent || "";
    const nav = [...document.querySelectorAll("nav.exam-bottom-nav-v15 button")].map((b) => b.textContent.trim());
    const bodySnippet = document.body.innerText.slice(0, 400);
    return { tree, loading, error, empty, heading, nav, bodySnippet };
  });
  console.log(JSON.stringify(info, null, 2));
}
await browser.close();
