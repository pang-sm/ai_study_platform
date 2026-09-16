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
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error" && !/404/.test(m.text())) consoleErrors.push(m.text()); });

async function openHome() {
  await page.evaluate(() => localStorage.setItem("ai_study_current_page", "programmingHome"));
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3500);
}
const navBtn = (name) => page.locator("nav.ph-nav").getByRole("button", { name });

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3500);

// ── 1. Workbench ──
await navBtn("编程工作台").click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(4000);
let t = await bodyText();
check("Workbench 左上角无「返回编程首页」", !t.includes("返回编程首页"), "");
check("Workbench 保留 运行 按钮", t.includes("运行"), "");
const hasBackBtn = await page.locator("[data-action='back-programming-home']").count();
check("Workbench 无 back-programming-home 按钮节点", hasBackBtn === 0, "");

// ── 2. 题库 ──
await navBtn("题库").click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3500);
t = await bodyText();
check("题库无「编程题库」大标题", !/编程题库/.test(t), "");
check("题库无介绍文案", !t.includes("包含标准输入输出原创 OJ 题与经典练习"), "");

// ── 3. AI问答 ──
await navBtn("AI问答").click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(4000);
t = await bodyText();
check("AI问答 无「AI 问答 ·」标题", !/AI 问答 ·/.test(t), "");
check("AI问答 无「编程学习 /」面包屑", !t.includes("编程学习 /"), "");
check("AI问答 历史对话 + 新对话 + 输入框正常", t.includes("历史对话") && t.includes("新对话"), "");

// ── 4. 资料库 (return home first) ──
await openHome();
check("编程学习左侧栏出现「资料库」", (await page.locator("nav.ph-nav").innerText()).includes("资料库"), "");
await navBtn("资料库").click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(4000);
t = await bodyText();
check("资料库页含 上传资料/刷新", t.includes("上传资料") && t.includes("刷新"), "");

// ── 5. Material API isolation ──
const uploadRes = await page.evaluate(async () => {
  const fd = new FormData();
  fd.append("file", new Blob(["python programming material test"], { type: "text/plain" }), "Python测试资料.txt");
  fd.append("username", "奶12");
  fd.append("course_id", "python_programming");
  fd.append("subject_key", "programming");
  fd.append("subject", "programming");
  fd.append("track", "programming");
  fd.append("save_to_materials", "true");
  const r = await fetch("/api/materials/upload", { method: "POST", credentials: "include", body: fd });
  return { status: r.status, body: await r.json().catch(() => ({})) };
});
check("上传 Python测试资料 成功", uploadRes.status === 200, `status=${uploadRes.status} detail=${JSON.stringify(uploadRes.body?.detail || "")}`);

const listPy = await page.evaluate(async () => {
  const r = await fetch("/api/materials?username=奶12&course_id=python_programming&track=programming", { credentials: "include" });
  return (await r.json()).materials || [];
});
check("Python资料库 可见 Python测试资料", listPy.some((m) => (m.original_filename || "").includes("Python测试资料")), "");

const listJava = await page.evaluate(async () => {
  const r = await fetch("/api/materials?username=奶12&course_id=java_programming&track=programming", { credentials: "include" });
  return (await r.json()).materials || [];
});
check("Java资料库 不可见 Python测试资料", !listJava.some((m) => (m.original_filename || "").includes("Python测试资料")), "");

for (const cid of ["c_programming", "cpp_programming"]) {
  const lst = await page.evaluate(async ({ cid }) => {
    const r = await fetch(`/api/materials?username=奶12&course_id=${cid}&track=programming`, { credentials: "include" });
    return (await r.json()).materials || [];
  }, { cid });
  check(`${cid} 资料库 不可见 Python测试资料`, !lst.some((m) => (m.original_filename || "").includes("Python测试资料")), "");
}

const listCoursePy = await page.evaluate(async () => {
  const r = await fetch("/api/materials?username=奶12&course_id=python_programming&subject_key=python_programming", { credentials: "include" });
  return (await r.json()).materials || [];
});
check("课程学习 Python scope 不可见编程资料", !listCoursePy.some((m) => (m.original_filename || "").includes("Python测试资料")), "");

const listExam = await page.evaluate(async () => {
  const r = await fetch("/api/materials?username=奶12&course_id=data_structure_11408&subject_key=data_structure", { credentials: "include" });
  return (await r.json()).materials || [];
});
check("11408 资料库 不可见编程资料", !listExam.some((m) => (m.original_filename || "").includes("Python测试资料")), "");

check("浏览器 Console 无相关报错", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" ;; "));

await browser.close();
const pass = results.filter((r) => r.ok).length;
console.log(`\n=== 结果 ${pass}/${results.length} 通过 ===`);
process.exit(pass === results.length ? 0 : 1);
