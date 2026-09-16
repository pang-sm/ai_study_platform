import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const bodyText = () => page.evaluate(() => document.body.innerText);
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(4000);
// go to knowledge, select a leaf, enter AI
await page.locator("nav.ph-nav").getByRole("button", { name: "知识点学习" }).click().catch(()=>{});
await page.waitForTimeout(4000);
const leaf = page.locator(".km-node-pill--leaf").nth(0);
if (await leaf.count()) { await leaf.click().catch(()=>{}); await page.waitForTimeout(1500); }
await page.locator(".km-actions button").click().catch(()=>{});
await page.waitForTimeout(4000);
let t = await bodyText();
const hasKpBefore = t.includes("返回知识点");
const kpBtnText = await page.getByRole("button", { name: /返回知识点/ }).innerText().catch(()=>"");
// refresh
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(4500);
t = await bodyText();
const hasKpAfter = t.includes("返回知识点");
const kpBtnText2 = await page.getByRole("button", { name: /返回知识点/ }).innerText().catch(()=>"");
console.log("进入知识点后上下文出现:", hasKpBefore, "|", kpBtnText);
console.log("刷新后上下文仍保留:", hasKpAfter, "|", kpBtnText2);
console.log("课程仍为Python:", /\bPython\b/.test(t), "且非其他学科:", !t.includes("计算机网络"));
console.log(kpBtnText === kpBtnText2 && hasKpBefore && hasKpAfter ? "PASS 知识点上下文刷新不丢失" : "FAIL");
await browser.close();
