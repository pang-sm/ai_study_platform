import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const BASE = "https://101.32.190.42";
const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const url = () => page.evaluate(() => window.location.pathname);
// navigate directly to programming home URL
await page.goto(BASE + "/programming/python_programming/home", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(4000);
console.log("after goto /home:", await url());
console.log("body has 编程学习:", (await page.evaluate(() => document.body.innerText)).includes("编程学习"));
// click 资料库
await page.locator("nav.ph-nav").getByRole("button", { name: "资料库" }).click({ timeout: 10000 }).catch(e=>console.log("click err", e.message));
await page.waitForTimeout(3000);
console.log("after click 资料库:", await url());
const t = await page.evaluate(() => document.body.innerText);
console.log("资料库 body 前 300:", t.slice(0, 300));
await browser.close();
