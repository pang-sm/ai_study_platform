import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const USER_AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "programming-workbench-online.json");
const ADMIN_AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "admin-dashboard-production.json");
const BASE = "https://101.32.190.42";
const USER_ID = 58; // 奶12

const results = [];
const check = (name, ok, detail = "") => {
  results.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
};

const browser = await chromium.launch({ headless: true });

const adminCtx = await browser.newContext({ storageState: ADMIN_AUTH, viewport: { width: 1440, height: 900 } });
const adminPage = await adminCtx.newPage();
await adminPage.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await adminPage.waitForTimeout(2500);

async function setMembership(plan, isEnabled) {
  const r = await adminPage.evaluate(async ({ plan, isEnabled, userId }) => {
    const res = await fetch(`/api/admin/users/${userId}/memberships`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ admin_username: "admin", memberships: { programming: { is_enabled: isEnabled, plan } } }),
    });
    return { status: res.status, body: await res.json().catch(() => ({})) };
  }, { plan, isEnabled, userId: USER_ID });
  return r;
}

const userCtx = await browser.newContext({ storageState: USER_AUTH, viewport: { width: 1440, height: 900 } });
const userPage = await userCtx.newPage();
const bodyText = () => userPage.evaluate(() => document.body.innerText);
const consoleErrors = [];
userPage.on("console", (m) => { if (m.type() === "error" && !/404/.test(m.text())) consoleErrors.push(m.text()); });

async function openHome() {
  await userPage.evaluate(() => localStorage.setItem("ai_study_current_page", "programmingHome"));
  await userPage.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
  await userPage.waitForTimeout(3500);
}

async function openProfile() {
  await openHome();
  await userPage.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await userPage.waitForTimeout(4000);
  return bodyText();
}

// ── Step 0: set user to free so ordering + free checks work ──
let r = await setMembership("free", false);
check("管理后台设置用户为 free 成功", r.status === 200, JSON.stringify(r.body));
await userPage.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await userPage.waitForTimeout(3000);

// ── C. Package catalog ──
const catResp = await userPage.evaluate(async () => {
  const r = await fetch("/api/membership/catalog?service_key=programming", { credentials: "include" });
  return { status: r.status, body: await r.json().catch(() => ({})) };
});
const plans = catResp.body?.plans || [];
const p = Object.fromEntries(plans.map((x) => [x.plan_code, x]));
check("套餐目录返回 4 档", plans.length === 4, JSON.stringify(plans.map((x) => x.plan_code)));
check("免费版 ¥0", p.free?.name === "免费版" && p.free?.price_cents === 0, p.free?.name);
check("编程进阶月卡 ¥49/月(30天)", p.monthly?.name === "编程进阶月卡" && p.monthly?.price_cents === 4900 && p.monthly?.duration_days === 30, `${p.monthly?.name} ${p.monthly?.price_cents}`);
check("实验与算法强化季卡 ¥129/季(90天)", p.quarterly?.name === "实验与算法强化季卡" && p.quarterly?.price_cents === 12900 && p.quarterly?.duration_days === 90, `${p.quarterly?.name} ${p.quarterly?.price_cents}`);
check("编程全能年卡 ¥399/年(365天)", p.full?.name === "编程全能年卡" && p.full?.price_cents === 39900 && p.full?.duration_days === 365, `${p.full?.name} ${p.full?.price_cents}`);
check("目录无 999999 假无限额度", !plans.some((x) => (x.quota?.ai_chat_daily_limit ?? 0) >= 999999), "");

// ── D. Checkout amount = catalog price ──
for (const [code, yuan] of [["monthly", 49], ["quarterly", 129], ["full", 399]]) {
  const o = await userPage.evaluate(async ({ code }) => {
    const res = await fetch("/api/membership/orders", {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
      body: JSON.stringify({ username: "奶12", service_key: "programming", target_plan: code }),
    });
    return { status: res.status, body: await res.json().catch(() => ({})) };
  }, { code });
  const amountYuan = o.body?.order?.amount_yuan ?? o.body?.amount_yuan ?? 0;
  check(`Checkout ${code} 订单金额 = ¥${yuan}`, amountYuan === yuan, `status=${o.status} amount_yuan=${amountYuan}`);
}

// ── A. Free user verification ──
let t = await openProfile();
check("Free 个人主页当前编程套餐 = 免费版", t.includes("免费版"), "");
check("Free AI问答/纠错 = 5次/天", /AI 问答 \/ 纠错额度/.test(t) && /\/\s*5\s*次/.test(t), "");
check("Free AI出题 = 3次/天", /AI 出题额度/.test(t) && /\/\s*3\s*次/.test(t), "");
check("Free 不显示 999999/无限", !/999999|无限/.test(t), "");

await openHome();
await userPage.locator("nav.ph-nav").getByRole("button", { name: "知识点学习" }).click({ timeout: 10000 }).catch(() => {});
await userPage.waitForTimeout(3500);
const cTab = userPage.locator(".km-language-tabs button", { hasText: "C" }).first();
if (await cTab.count()) { await cTab.click({ timeout: 10000 }).catch(() => {}); await userPage.waitForTimeout(2000); }
await userPage.locator("nav.ph-nav").getByRole("button", { name: "AI问答" }).click({ timeout: 10000 }).catch(() => {});
await userPage.waitForTimeout(4000);
t = await bodyText();
check("Free 进入 AI问答（编程学习 → C）", t.includes("编程 AI 问答") && /\bC\b/.test(t), "");
await userPage.fill("textarea.examchat-input", "用一句话介绍 C 语言的指针（套餐验证）");
await userPage.click("button.examchat-send-btn");
let freeSent = false;
for (let i = 0; i < 20; i++) {
  await userPage.waitForTimeout(3000);
  t = await bodyText();
  if (t.includes("指针") && !t.includes("AI 正在思考")) { freeSent = true; break; }
  if (t.includes("额度已用完") || t.includes("已达上限")) break;
}
check("Free AI问答发送消息成功（额度一致）", freeSent, "");

// ── B. Quarterly user verification ──
r = await setMembership("quarterly", true);
check("管理后台设置用户为 quarterly 成功", r.status === 200, JSON.stringify(r.body));
t = await openProfile();
check("季卡 个人主页 = 实验与算法强化季卡", t.includes("实验与算法强化季卡"), "");
check("季卡 AI问答/纠错 = 200次/天", /AI 问答 \/ 纠错额度/.test(t) && /\/\s*200\s*次/.test(t), "");
check("季卡 AI出题 = 60次/天", /AI 出题额度/.test(t) && /\/\s*60\s*次/.test(t), "");

await openHome();
await userPage.locator("nav.ph-nav").getByRole("button", { name: "AI问答" }).click({ timeout: 10000 }).catch(() => {});
await userPage.waitForTimeout(4000);
await userPage.fill("textarea.examchat-input", "用一句话介绍 Python 的生成器（季卡验证）");
await userPage.click("button.examchat-send-btn");
let paidSent = false;
for (let i = 0; i < 20; i++) {
  await userPage.waitForTimeout(3000);
  t = await bodyText();
  if (t.includes("生成器") && !t.includes("AI 正在思考")) { paidSent = true; break; }
  if (t.includes("额度已用完") || t.includes("已达上限")) break;
}
check("季卡 AI问答发送消息成功", paidSent, "");

// restore original (full / 编程全能年卡)
await setMembership("full", true);
console.log("(已把测试用户 58 恢复为 full/编程全能年卡)");

check("浏览器 Console 无相关报错", consoleErrors.length === 0, consoleErrors.slice(0, 3).join(" ;; "));

await browser.close();
const pass = results.filter((r) => r.ok).length;
console.log(`\n=== 结果 ${pass}/${results.length} 通过 ===`);
process.exit(pass === results.length ? 0 : 1);
