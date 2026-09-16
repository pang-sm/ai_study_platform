import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3500);
// select Python language via 知识点学习 then AI问答
await page.locator("nav.ph-nav").getByRole("button", { name: "知识点学习" }).click().catch(()=>{});
await page.waitForTimeout(3500);
const pyTab = page.locator(".km-language-tabs button", { hasText: "Python" }).first();
if (await pyTab.count()) { await pyTab.click().catch(()=>{}); await page.waitForTimeout(1500); }
await page.locator("nav.ph-nav").getByRole("button", { name: "AI问答" }).click().catch(()=>{});
await page.waitForTimeout(4000);
// open + menu, click 引用资料
await page.locator(".examchat-plus-btn").click().catch(()=>{});
await page.waitForTimeout(1000);
const menuText = await page.evaluate(() => document.body.innerText);
console.log("+ 菜单:", menuText.includes("引用资料") ? "有引用资料" : "无引用资料");
await page.getByRole("button", { name: /引用资料/ }).first().click().catch(()=>{});
await page.waitForTimeout(3000);
const t = await page.evaluate(() => document.body.innerText);
console.log("资料选择器含 Python测试资料:", t.includes("Python测试资料"));
console.log("资料选择器不含 Java 测试资料:", !t.includes("Java测试资料"));
await browser.close();
