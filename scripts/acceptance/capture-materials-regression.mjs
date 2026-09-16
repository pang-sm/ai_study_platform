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
const netLog = [];
page.on("request", (req) => {
  const u = req.url();
  if (u.includes("/api/materials") || u.includes("/course-learning/courses")) {
    netLog.push({ method: req.method(), url: u, postData: req.postData() || "" });
  }
});
page.on("response", async (res) => {
  const u = res.url();
  if (u.includes("/api/materials") && !u.includes("/upload")) {
    try { const j = await res.json(); netLog.push({ responseUrl: u, status: res.status(), total: j?.materials?.length, materials: (j?.materials||[]).map(m => ({id:m.id, course_id:m.course_id, subject_key:m.subject_key, fn:m.file_name})) }); } catch {}
  }
});

const body = () => page.evaluate(() => document.body.innerText);

// Switch to course-learning track
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到课程", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
console.log("after switch URL:", page.url());
let t = await body();
console.log("course-learning home text (first 800):\n", t.slice(0, 800));

// find a course card and click it
const courseCard = await page.evaluate(() => {
  const els = Array.from(document.querySelectorAll("a,button,div,[role=button]")).filter(el => {
    const txt = (el.innerText || "").trim();
    return /计算机组成|数据结构|操作系统|计算机网络/.test(txt) && txt.length < 20;
  });
  return els.map(e => e.innerText.trim().slice(0,30)).slice(0,10);
});
console.log("course candidates:", JSON.stringify(courseCard));

// click first course card (try clicking a div that looks like a course)
const clicked = await page.evaluate(() => {
  const els = Array.from(document.querySelectorAll("*")).filter(el => {
    const txt = (el.innerText || "").trim();
    return (txt === "计算机组成原理" || txt === "数据结构" || txt === "操作系统" || txt === "计算机网络");
  });
  if (els.length) { els[0].click(); return els[0].innerText; }
  return null;
});
console.log("clicked course:", clicked);
await page.waitForTimeout(3500);
console.log("after course click URL:", page.url());

// Click 资料库 nav
await page.getByText("资料库", { exact: true }).first().click({ timeout: 10000 }).catch((e) => console.log("资料库 click err", e.message));
await page.waitForTimeout(3500);
console.log("after 资料库 URL:", page.url());

console.log("\n===== NETWORK LOG (materials) =====");
for (const l of netLog) console.log(JSON.stringify(l));

await browser.close();
