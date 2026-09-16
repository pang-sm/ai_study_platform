// v16.5.1 — Knowledge UI refinement + Auth legal links verification.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000";
const SUBJECT = "computer_organization";
const USER = `mobile_v1651_${Date.now()}`;
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../verification-results/mobile-v1651");
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const api = ctx.request;
const results = [];
const check = (n, ok, extra = "") => { results.push([n, ok]); console.log(`${ok ? "PASS" : "FAIL"} ${n}${extra ? " — " + extra : ""}`); };

try {
  await api.post(`${API}/register`, { data: { username: USER, password: "v1651test" } });
  const page = await ctx.newPage();
  await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.evaluate((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify({ username: u, nickname: "V1651", onboarding_completed: true })), USER);

  // ── Auth legal links (no localStorage needed to see auth; clear it) ──
  await page.evaluate(() => localStorage.removeItem("ai_study_platform_user"));
  await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(1200);
  const legal = page.locator(".auth-legal");
  const legalVisible = await legal.isVisible().catch(() => false);
  check("auth legal footer visible", legalVisible);
  const termsHref = await page.locator(".auth-legal a[href='/terms']").getAttribute("href").catch(() => "");
  const privacyHref = await page.locator(".auth-legal a[href='/privacy']").getAttribute("href").catch(() => "");
  check("terms link href=/terms", termsHref === "/terms", termsHref);
  check("privacy link href=/privacy", privacyHref === "/privacy", privacyHref);
  const legalText = await legal.innerText().catch(() => "");
  check("legal text mentions 用户协议 + 隐私政策", legalText.includes("用户协议") && legalText.includes("隐私政策"), legalText.replace(/\s+/g, " "));
  // switch to register and re-check
  await page.getByText("没有账号？注册").first().click();
  await page.waitForTimeout(500);
  const legalRegVisible = await page.locator(".auth-legal").isVisible().catch(() => false);
  check("register page also shows legal footer", legalRegVisible);
  await page.screenshot({ path: path.join(OUT, "07-login-390.png") }).catch(() => {});

  // viewport screenshots for auth
  for (const vp of [{ w: 360, h: 800, n: "06-login-360" }, { w: 390, h: 844, n: "07-login-390" }, { w: 412, h: 915, n: "08-login-412" }]) {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(OUT, vp.n + ".png") }).catch(() => {});
  }
  for (const vp of [{ w: 360, h: 800, n: "09-register-360" }, { w: 390, h: 844, n: "10-register-390" }, { w: 412, h: 915, n: "11-register-412" }]) {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => localStorage.removeItem("ai_study_platform_user"));
    await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(800);
    await page.getByText("没有账号？注册").first().click().catch(() => {});
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT, vp.n + ".png") }).catch(() => {});
  }

  // ── Knowledge tree ──
  await page.setViewportSize({ width: 390, height: 844 });
  await page.evaluate((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify({ username: u, nickname: "V1651", onboarding_completed: true })), USER);
  await page.goto(`${WEB}/m/exam11408/${SUBJECT}/chapters`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2200);
  const collapsed = await page.evaluate(() => ({
    chapterCards: document.querySelectorAll(".v16-tree-node.depth-0").length,
    chapterCardHasBg: (() => { const el = document.querySelector(".v16-tree-node.depth-0"); return el ? getComputedStyle(el).backgroundColor !== "rgba(0, 0, 0, 0)" && getComputedStyle(el).borderRadius !== "0px" : false; })(),
    openChildren: document.querySelectorAll(".v16-tree-children").length,
    counts: document.body.innerText.match(/\d+题/) ? true : false,
    introText: document.body.innerText.includes("展开知识图谱") || document.body.innerText.includes("选择练习方式"),
    subjectName: document.body.innerText.includes("计算机组成原理"),
  }));
  check("knowledge default: top-level chapter cards present", collapsed.chapterCards > 0, `${collapsed.chapterCards} cards`);
  check("chapter card has background + radius (not bare text)", collapsed.chapterCardHasBg);
  check("knowledge default collapsed (no children expanded)", collapsed.openChildren === 0, `openChildren=${collapsed.openChildren}`);
  check("knowledge: no question counts", !collapsed.counts);
  check("knowledge: no duplicate intro text", !collapsed.introText);
  check("knowledge: subject name shown", collapsed.subjectName);
  await page.screenshot({ path: path.join(OUT, "01-knowledge-collapsed.png") }).catch(() => {});

  // expand first chapter -> level 1
  await page.locator(".v16-tree-toggle").first().click();
  await page.waitForTimeout(500);
  const l1 = await page.evaluate(() => ({ children: document.querySelectorAll(".v16-tree-children").length, depth1: document.querySelectorAll(".v16-tree-node.depth-1").length }));
  check("expand chapter shows level-1 sections", l1.children > 0 && l1.depth1 > 0, `children=${l1.children} depth1=${l1.depth1}`);
  await page.screenshot({ path: path.join(OUT, "02-knowledge-level1.png") }).catch(() => {});

  // expand deeper -> leaves
  const toggles = page.locator(".v16-tree-toggle");
  const tc = await toggles.count();
  for (let i = 0; i < Math.min(tc, 4); i++) { await toggles.nth(i).click().catch(() => {}); await page.waitForTimeout(200); }
  await page.waitForTimeout(500);
  const leaves = await page.evaluate(() => ({
    dots: document.querySelectorAll(".v16-tree-dot").length,
    badges: document.querySelectorAll(".v16-status-badge").length,
    leafArrows: document.querySelectorAll(".v16-tree-row.is-leaf .v16-tree-toggle").length,
    branchArrows: [...document.querySelectorAll(".v16-tree-node")].map(n => n.querySelectorAll(":scope > .v16-tree-row > .v16-tree-toggle").length).filter(c => c > 1).length,
  }));
  check("leaves show dots", leaves.dots > 0, `${leaves.dots} dots`);
  check("leaves show status badges", leaves.badges > 0, `${leaves.badges} badges`);
  check("leaves have 0 arrows", leaves.leafArrows === 0, `leafArrows=${leaves.leafArrows}`);
  check("each branch has max 1 arrow", leaves.branchArrows === 0, `multiArrowBranches=${leaves.branchArrows}`);
  await page.screenshot({ path: path.join(OUT, "04-knowledge-leaves.png") }).catch(() => {});

  // open a leaf sheet
  const leafSel = page.locator(".v16-tree-row.is-leaf .v16-tree-select").first();
  if (await leafSel.isVisible().catch(() => false)) {
    await leafSel.click();
    await page.waitForTimeout(600);
    const sheet = await page.locator(".knowledge-sheet-v14").isVisible().catch(() => false);
    check("leaf click opens bottom sheet", sheet);
    await page.screenshot({ path: path.join(OUT, "05-knowledge-sheet.png") }).catch(() => {});
  }

  // 03-knowledge-level2 (a mid-expanded view)
  await page.screenshot({ path: path.join(OUT, "03-knowledge-level2.png") }).catch(() => {});
} catch (e) {
  console.error("FATAL", e.message);
} finally {
  await browser.close();
  const allPass = results.every(([, ok]) => ok);
  console.log(`\n===== v16.5.1 RESULT ===== PASS=${allPass} (${results.filter(([, ok]) => ok).length}/${results.length})`);
  console.log(`TEST_USER=${USER}`);
}
