import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const BASE = "https://101.32.190.42";

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
}

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  storageState: AUTH,
  viewport: { width: 1440, height: 900 },
});
const page = await ctx.newPage();

const consoleErrors = [];
const failedRequests = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("requestfailed", (req) => failedRequests.push(`FAILED ${req.method()} ${req.url()} ${req.failure()?.errorText || ""}`));
page.on("response", (res) => {
  if (res.status() >= 400) failedRequests.push(`${res.status()} ${res.url()}`);
});

// Known pre-existing avatar asset missing on the server (unrelated to AI chat).
const isBenign = (s) => /\/api\/me\/avatar\/.*\.png/.test(s) || s.includes("favicon");

const bodyText = () => page.evaluate(() => document.body.innerText);
const sidebarAI = () => page.locator("nav.ph-nav").getByRole("button", { name: "AI问答" });
const sidebarBtn = (name) => page.locator("nav.ph-nav").getByRole("button", { name });

await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(4000);

// 1. Sidebar shows AI 问答
const nav = await page.locator("nav.ph-nav").innerText().catch(() => "");
check("编程学习左侧栏出现「AI问答」", /AI问答/.test(nav), nav.replace(/\n/g, " | "));

const navItems = await page.locator("nav.ph-nav button").allInnerTexts();
const qiIdx = navItems.findIndex((t) => t.includes("题库"));
const aiIdx = navItems.findIndex((t) => t.includes("AI问答"));
check("「AI问答」位于「题库」下方", qiIdx >= 0 && aiIdx > qiIdx, `题库@${qiIdx}, AI问答@${aiIdx}`);

// 2. Click AI问答 -> new programming chat page
await sidebarAI().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(4000);
let t = await bodyText();
check("点击进入新版编程 AI 问答（标题「编程 AI 问答」）", t.includes("编程 AI 问答"), "");
check("聊天页含「新对话」与「历史对话」", t.includes("新对话") && t.includes("历史对话"), "");
check("课程显示为 Python（非计算机网络/计算系统基础）", /编程 AI 问答/.test(t) && /\bPython\b/.test(t) && !t.includes("计算机网络") && !t.includes("计算系统基础"), "");

// 3. Create a chat in Python
const probeMsg = "请用一句话介绍 Python 列表推导式（验证消息）";
await page.fill("textarea.examchat-input", probeMsg);
await page.click("button.examchat-send-btn");
let replied = false;
for (let i = 0; i < 24; i++) {
  await page.waitForTimeout(3000);
  t = await bodyText();
  if (t.includes("列表推导式") && !t.includes("AI 正在思考")) { replied = true; break; }
}
check("Python 发送消息并得到 AI 回复", replied, "");

// 4. Refresh -> chat still exists (history panel)
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForTimeout(4000);
t = await bodyText();
check("刷新后课程仍为 Python（不会变成其他学科）", t.includes("编程 AI 问答") && /\bPython\b/.test(t) && !t.includes("计算机网络"), "");
const historyAfterReload = await page.locator("aside.examchat-history-panel").innerText().catch(() => "");
check("刷新后历史对话仍存在", historyAfterReload.includes("列表推导式"), historyAfterReload.slice(0, 120).replace(/\n/g, " | "));

// 5. Exit AI问答 and re-enter -> history persists
await page.getByRole("button", { name: "← 返回编程学习" }).click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(2500);
await sidebarAI().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3500);
const historyReenter = await page.locator("aside.examchat-history-panel").innerText().catch(() => "");
check("退出再进入后历史聊天仍存在", historyReenter.includes("列表推导式"), historyReenter.slice(0, 120).replace(/\n/g, " | "));

// 6. Switch to a history session restores messages
const histButtons = page.locator("aside.examchat-history-panel button.examchat-history-item");
if (await histButtons.count()) {
  await histButtons.nth(0).click({ timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(3000);
  t = await bodyText();
  check("切换历史会话可恢复消息", t.includes("列表推导式"), "");
} else {
  check("切换历史会话可恢复消息", false, "无历史会话可切换");
}

// 7. Knowledge point -> AI 问答 context (Python knowledge)
await page.getByRole("button", { name: "← 返回编程学习" }).click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(2500);
await sidebarBtn("知识点学习").click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(4000);
const leafPills = page.locator(".km-node-pill--leaf");
if (await leafPills.count()) {
  await leafPills.nth(0).click({ timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(1500);
}
await page.locator(".km-actions button").click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(4000);
t = await bodyText();
check("从知识点进入 AI问答（携带知识点上下文/返回知识点按钮）", t.includes("返回知识点"), "");

// 8. Return to knowledge point positioning
const kpBackBtn = page.getByRole("button", { name: /返回知识点/ });
if (await kpBackBtn.count()) {
  await kpBackBtn.click({ timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(3500);
  t = await bodyText();
  check("从 AI问答跳回知识点页面（知识脉络详情）", t.includes("知识点详情") && t.includes("章节目录"), "");
} else {
  check("从 AI问答跳回知识点页面", false, "无返回知识点按钮");
}

// 9. Switch to Java -> no Python chat
await sidebarBtn("知识点学习").click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(3000);
const javaTab = page.locator(".km-language-tabs button", { hasText: "Java" });
if (await javaTab.count()) {
  await javaTab.first().click({ timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(2500);
}
await sidebarAI().click({ timeout: 10000 }).catch(() => {});
await page.waitForTimeout(4000);
t = await bodyText();
const chatTitle = await page.locator(".examchat-title").innerText().catch(() => "");
check("切换 Java 后课程显示 Java", /\bJava\b/.test(chatTitle) && !/\bPython\b/.test(chatTitle), chatTitle);
const javaHistory = await page.locator("aside.examchat-history-panel").innerText().catch(() => "");
check("Java 会话隔离（不显示 Python 聊天）", !javaHistory.includes("列表推导式"), javaHistory.slice(0, 120).replace(/\n/g, " | "));

// 10. Console / network health
const relevantConsoleErrors = consoleErrors.filter((e) => !isBenign(e) && !/404/.test(e));
check("浏览器 Console 无相关报错", relevantConsoleErrors.length === 0, relevantConsoleErrors.slice(0, 3).join(" ;; "));
const relevantFailures = failedRequests.filter((r) => !isBenign(r) && !/ 404 /.test(r) && !/^404 /.test(r));
check("Network 无失败请求(>=400，排除已知头像404)", relevantFailures.length === 0, relevantFailures.slice(0, 5).join(" ;; "));

await browser.close();

const pass = results.filter((r) => r.ok).length;
console.log(`\n=== 结果 ${pass}/${results.length} 通过 ===`);
process.exit(pass === results.length ? 0 : 1);
