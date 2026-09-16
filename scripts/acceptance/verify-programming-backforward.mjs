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
const results = [];
const check = (n, ok, d="") => { results.push(ok); console.log(`${ok?"PASS":"FAIL"}  ${n}${d?"  — "+d:""}`); };

// Python 首页 → 资料库 → AI问答
await page.goto(BASE + "/programming/python_programming/home", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3500);
await page.locator("nav.ph-nav").getByRole("button", { name: "资料库" }).click().catch(()=>{});
await page.waitForTimeout(2500);
check("点击资料库后 URL = materials", (await url()).includes("/materials"), await url());
await page.locator("nav.ph-nav").getByRole("button", { name: "AI问答" }).click().catch(()=>{});
await page.waitForTimeout(3000);
check("点击 AI问答后 URL = chat", (await url()).includes("/chat"), await url());
// Back → materials
await page.goBack({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
check("Back 后回到资料库", (await url()).includes("/materials"), await url());
check("Back 后显示 Python 资料", (await page.evaluate(()=>document.body.innerText)).includes("Python测试资料.txt"), "");
// Back → home
await page.goBack({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
check("Back 后回到首页", (await url()).includes("/home"), await url());
// Forward → materials
await page.goForward({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
check("Forward 后回到资料库", (await url()).includes("/materials"), await url());
await browser.close();
const pass = results.filter(Boolean).length;
console.log(`\n=== ${pass}/${results.length} 通过 ===`);
process.exit(pass === results.length ? 0 : 1);
