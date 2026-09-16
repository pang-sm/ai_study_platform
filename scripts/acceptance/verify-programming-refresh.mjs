import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const BASE = "https://101.32.190.42";

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const bodyText = () => page.evaluate(() => document.body.innerText);
const url = () => page.evaluate(() => window.location.pathname);
const navCount = () => page.locator("nav.ph-nav").count();
const navBtn = (name) => page.locator("nav.ph-nav").getByRole("button", { name });

// ── 1. Direct URL → Python 资料库 ──
await page.goto(BASE + "/programming/python_programming/materials", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(5000);
let t = await bodyText();
check("直接 URL 进入 Python 资料库", (await navCount()) > 0 && !t.includes("页面加载异常"), "");
check("资料库含 Python测试资料.txt", t.includes("Python测试资料.txt"), "");
check("资料库含 coa26_第1讲.pdf", t.includes("coa26_第1讲.pdf"), "");

// ── 2. F5 reload ──
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(5000);
t = await bodyText();
check("F5 后仍在编程资料库（非课程学习）", (await navCount()) > 0 && !t.includes("页面加载异常"), "");
check("F5 后 URL 不变", (await url()).includes("/programming/python_programming/materials"), await url());
check("F5 后仍显示 Python 资料", t.includes("Python测试资料.txt") || t.includes("coa26_第1讲.pdf"), "");

// ── 3. Ctrl+F5 (hard reload via direct goto) ──
await page.goto(BASE + "/programming/python_programming/materials", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(5000);
check("Ctrl+F5 后仍在编程资料库", (await navCount()) > 0, "");

// ── 4. AI问答 URL + F5 ──
await page.goto(BASE + "/programming/python_programming/chat", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(5000);
t = await bodyText();
check("AI问答 直接 URL 进入（无 AI 问答 · 标题）", !t.includes("页面加载异常") && !/AI 问答 ·/.test(t), "");
check("AI问答 有历史对话/新对话", t.includes("历史对话") || t.includes("新对话"), "");
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(5000);
check("AI问答 F5 后仍在 AI问答", (await url()).includes("/chat"), await url());

// ── 5. New tab (fresh page, same context) → Java 资料库 ──
const page2 = await ctx.newPage();
await page2.goto(BASE + "/programming/java_programming/materials", { waitUntil: "domcontentloaded", timeout: 60000 });
await page2.waitForTimeout(5000);
t = await page2.evaluate(() => document.body.innerText);
check("新标签 Java 资料库 URL 正确", (await page2.evaluate(() => window.location.pathname)).includes("/programming/java_programming/materials"), "");
check("Java 资料库不显示 Python 资料", !t.includes("Python测试资料.txt") && !t.includes("coa26_第1讲.pdf"), "");
await page2.close();

// ── 6. Material isolation (API) ──
const py = await page.evaluate(async () => {
  const r = await fetch("/api/materials?username=奶12&course_id=python_programming&track=programming", { credentials: "include" });
  return (await r.json()).materials || [];
});
check("Python 资料库只含 programming+python 资料", py.some((m) => m.original_filename.includes("Python测试资料")), "");
check("Python 资料库不含 11408/course 资料", !py.some((m) => (m.course_id || "").includes("_11408") || (m.subject_key || "") !== "programming"), "");

await browser.close();
const pass = results.filter((r) => r.ok).length;
console.log(`\n=== 结果 ${pass}/${results.length} 通过 ===`);
process.exit(pass === results.length ? 0 : 1);
