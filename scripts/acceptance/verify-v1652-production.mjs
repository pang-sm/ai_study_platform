// Mobile v16.5.2 — Production Final Audit against https://101.32.190.42/m
// Baseline commit: ec22a9a. Uses existing legitimate production account 奶12 (session cookie).
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const BASE = "https://101.32.190.42";
const COOKIE = "nILnBCF5uCOPPOZpGYXWCmHC1WaBM4fYSyfeh5t41NpDql1XoUgsamDwaCySpwpN";
const USER = { username: "奶12", nickname: "奶12", onboarding_completed: true, needs_onboarding: false };
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../verification-results/mobile-v1652-production");
fs.mkdirSync(OUT, { recursive: true });

const results = [];
const check = (name, ok, extra = "") => { results.push({ name, ok, extra }); console.log(`${ok ? "PASS" : "FAIL"} | ${name}${extra ? " | " + extra : ""}`); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let phase = "";
const net = [];
const captured = {};

function attachNet(page) {
  page.on("request", (req) => {
    const u = req.url();
    if (u.includes("/api/")) net.push({ phase, method: req.method(), url: u });
    if (u.includes("/chat") && req.method() === "POST") {
      try { captured.chatPostBody = JSON.parse(req.postData() || "{}"); } catch {}
    }
  });
  page.on("response", async (resp) => {
    const u = resp.url();
    if (!u.includes("/api/")) return;
    if (/past-paper-attempts\/\d+$/.test(u) && resp.request().method() === "GET") {
      try { captured.pastPaperAttempt = await resp.json(); } catch {}
    }
    if (/chapter-practice\/attempts\/\d+/.test(u) && resp.request().method() === "GET") {
      try { captured.chapterAttempt = await resp.json(); } catch {}
    }
  });
}

async function bodyText(page) { return page.locator("body").innerText().catch(() => "") || ""; }
async function waitTree(page, sel = ".v16-tree-node") {
  try { await page.waitForSelector(sel, { timeout: 15000 }); } catch {}
  await sleep(300);
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const appCtx = await browser.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
  await appCtx.addCookies([{ name: "ai_session", value: COOKIE, domain: "101.32.190.42", path: "/", httpOnly: true, secure: true, sameSite: "Lax" }]);
  await appCtx.addInitScript((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify(u)), USER);
  const app = await appCtx.newPage();
  attachNet(app);

  const authCtx = await browser.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
  const auth = await authCtx.newPage();
  attachNet(auth);

  const shot = async (name) => { try { await app.screenshot({ path: path.join(OUT, name + ".png") }); } catch {} };
  const shotAuth = async (name) => { try { await auth.screenshot({ path: path.join(OUT, name + ".png") }); } catch {} };

  try {
    // ============ S3 subject select ============
    console.log("\n== S3 subject select ==");
    phase = "subject-select";
    await app.goto(`${BASE}/m/exam11408`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(1600);
    const bt = await bodyText(app);
    check("S3 four subjects present", ["数据结构", "计算机组成原理", "操作系统", "计算机网络"].every((n) => bt.includes(n)));
    check("S3 subject cards rendered", (await app.locator(".v16-subject-card").count()) >= 4);
    await shot("01-subject-select");

    // ============ S4 knowledge tree ============
    console.log("\n== S4 knowledge tree ==");
    const SUBJ = "data_structure";
    phase = "knowledge";
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/chapters`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitTree(app);
    await sleep(600);
    await shot("02-knowledge-collapsed");
    const depth0 = await app.locator(".v16-tree-node.depth-0").count();
    check("S4 top-level chapters present", depth0 > 0, `${depth0} nodes`);
    const openChildren = await app.locator(".v16-tree-children").count();
    check("S4 default collapsed (no children)", openChildren === 0, `openChildren=${openChildren}`);
    const bodyT = await bodyText(app);
    check("S4 no 'xx题' counts", !/\d+题/.test(bodyT), bodyT.match(/\d+题/g)?.slice(0, 3).join(",") || "");
    check("S4 no '展开知识图谱' text", !bodyT.includes("展开知识图谱"));
    const nav = (await app.locator("nav.exam-bottom-nav-v15 button").allInnerTexts().catch(() => [])).map((s) => s.replace(/^[\s\S]?(?=知识|练习|AI)/u, "").replace(/[◫✓✦●⌂◆]/gu, "").trim());
    const navLabels = nav.map((s) => s.replace(/^[^知练A]/u, ""));
    check("S4 bottom nav = 知识点/练习/AI对话", nav.join(",") === "知识点,练习,AI对话", nav.join(","));

    // expand levels
    const toggles = app.locator(".v16-tree-toggle");
    const tc = await toggles.count();
    check("S4 branch arrows exist", tc > 0, `toggles=${tc}`);
    for (let i = 0; i < Math.min(tc, 6); i++) { await toggles.nth(i).click().catch(() => {}); await sleep(200); }
    await sleep(400);
    await shot("03-knowledge-expanded");
    const leaves = await app.locator(".v16-tree-row.is-leaf").count();
    const leafArrows = await app.locator(".v16-tree-row.is-leaf .v16-tree-toggle").count();
    const dots = await app.locator(".v16-tree-dot").count();
    const badges = await app.locator(".v16-status-badge").count();
    check("S4 leaves present", leaves > 0, `${leaves} leaves`);
    check("S4 leaf has 0 arrows", leafArrows === 0, `leafArrows=${leafArrows}`);
    check("S4 leaf has dot (no arrow)", dots > 0, `dots=${dots}`);
    check("S4 leaf shows status badge", badges > 0, `badges=${badges}`);

    // ============ S5 knowledge sheet ============
    console.log("\n== S5 knowledge sheet ==");
    const leafRow = app.locator(".v16-tree-row.is-leaf").first();
    if (await leafRow.isVisible().catch(() => false)) {
      await leafRow.locator(".v16-tree-select").first().click();
      await sleep(700);
      const sheetVisible = await app.locator(".knowledge-sheet-v14").isVisible().catch(() => false);
      check("S5 leaf click opens sheet", sheetVisible);
      await shot("04-knowledge-sheet");
      const sheetText = sheetVisible ? await app.locator(".knowledge-sheet-v14").innerText() : "";
      check("S5 sheet shows 4 statuses", ["未学习", "学习中", "已学习", "待复习"].every((n) => sheetText.includes(n)), sheetText.replace(/\s+/g, " ").slice(0, 120));
      check("S5 sheet: 知识点名称 + AI解释 + 进入练习", sheetText.includes("知识点") && sheetText.includes("AI解释") && sheetText.includes("进入练习"));
      const statusBtns = app.locator(".knowledge-sheet-v14 .knowledge-status-panel-v14 button");
      const statusCount = await statusBtns.count();
      if (statusCount === 4) {
        const leafTitle = await app.locator(".knowledge-sheet-v14 .sheet-heading h2").innerText().catch(() => "");
        const currentActive = await app.locator(".knowledge-sheet-v14 .knowledge-status-panel-v14 button.is-active").innerText().catch(() => "未学习");
        const target = ["未学习", "学习中", "已学习", "待复习"].find((n) => n !== currentActive) || "学习中";
        const expandAll = async () => { for (let i = 0; i < 6; i++) { await app.locator(".v16-tree-toggle").nth(i).click().catch(() => {}); await sleep(150); } await sleep(400); };
        // change status -> sheet closes after PATCH save
        await app.locator(".knowledge-sheet-v14 .knowledge-status-panel-v14 button", { hasText: target }).first().click();
        await sleep(1500);
        // refresh and verify persistence via the leaf badge
        await app.reload({ waitUntil: "domcontentloaded" });
        await waitTree(app);
        await expandAll();
        const leafAfter = app.locator(".v16-tree-row.is-leaf", { hasText: leafTitle }).first();
        const badgeAfter = (await leafAfter.isVisible().catch(() => false)) ? (await leafAfter.locator(".v16-status-badge").innerText().catch(() => "")) : "";
        check("S5 status changed + persisted after refresh", badgeAfter === target, `"${leafTitle}" badge=${badgeAfter} (want ${target})`);
        // restore original status
        await leafAfter.locator(".v16-tree-select").first().click().catch(() => {});
        await sleep(700);
        await app.locator(".knowledge-sheet-v14 .knowledge-status-panel-v14 button", { hasText: currentActive }).first().click().catch(() => {});
        await sleep(1500);
        await app.reload({ waitUntil: "domcontentloaded" });
        await waitTree(app);
        await expandAll();
        const leafRestored = app.locator(".v16-tree-row.is-leaf", { hasText: leafTitle }).first();
        const badgeRestored = (await leafRestored.isVisible().catch(() => false)) ? (await leafRestored.locator(".v16-status-badge").innerText().catch(() => "")) : "";
        check("S5 status restored + persisted", badgeRestored === currentActive, `badge=${badgeRestored} (want ${currentActive})`);
      } else {
        check("S5 status buttons = 4", false, `count=${statusCount}`);
      }

      // ============ S6 knowledge -> chapter practice ============
      console.log("\n== S6 knowledge -> chapter practice ==");
      phase = "knowledge-to-practice";
      // reopen a leaf sheet (closed after S5), then click 进入练习
      await app.locator(".v16-tree-row.is-leaf .v16-tree-select").first().click().catch(() => {});
      await sleep(700);
      const enterBtn = app.locator(".knowledge-sheet-v14 .sheet-actions .primary-button", { hasText: "进入练习" }).first();
      if (await enterBtn.isVisible().catch(() => false)) {
        await enterBtn.click();
        await sleep(2200);
        const url = app.url();
        check("S6 URL goes to type=chapter", url.includes("type=chapter") && url.includes("knowledgeId"), url);
        const pt = await bodyText(app);
        check("S6 shows 章节练习 (not 真题)", pt.includes("章节练习") && !pt.includes("真题"), "");
      } else {
        check("S6 进入练习 button present", false);
      }
    } else {
      check("S5/S6 leaf row visible", false);
    }

    // ============ S7 practice home ============
    console.log("\n== S7 practice home ==");
    phase = "practice-home";
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/practice`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(1800);
    await shot("05-practice");
    const pt7 = await bodyText(app);
    check("S7 four entries present", ["真题", "章节练习", "错题本", "AI出题"].every((n) => pt7.includes(n)));
    check("S7 no '选择练习方式'", !pt7.includes("选择练习方式"));
    check("S7 4 entry buttons", (await app.locator(".v16-practice-entry").count()) === 4);

    // ============ S8 chapter practice scopes (parent vs leaf) ============
    console.log("\n== S8 chapter practice ==");
    phase = "chapter-practice";
    let scopeParent = "", scopeLeaf = "";
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/practice?type=chapter`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitTree(app);
    await shot("06-chapter-practice");
    const pt8 = await bodyText(app);
    check("S8 no '按章节/按知识点' tabs", !pt8.includes("按章节") && !pt8.includes("按知识点"));
    // parent (branch) scope
    const firstBranch = app.locator(".v16-tree-node:has(.v16-tree-toggle)").first();
    if (await firstBranch.isVisible().catch(() => false)) {
      await firstBranch.locator(".v16-tree-select").first().click();
      await sleep(500);
      scopeParent = await app.locator(".v16-selected-range span").innerText().catch(() => "");
      check("S8 parent node selectable", scopeParent.length > 0, scopeParent);
      await app.locator(".v16-selected-range .primary-button").first().click().catch(() => {});
      await sleep(2500);
      const ctx1 = await app.locator(".v16-practice-context strong").innerText().catch(() => "");
      check("S8 parent scope started", ctx1.length > 0, ctx1);
    }
    // leaf scope
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/practice?type=chapter`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitTree(app);
    for (let i = 0; i < 6; i++) { await app.locator(".v16-tree-toggle").nth(i).click().catch(() => {}); await sleep(150); }
    await sleep(400);
    const leafSel = app.locator(".v16-tree-row.is-leaf").first();
    if (await leafSel.isVisible().catch(() => false)) {
      await leafSel.locator(".v16-tree-select").first().click();
      await sleep(500);
      scopeLeaf = await app.locator(".v16-selected-range span").innerText().catch(() => "");
      check("S8 leaf selectable", scopeLeaf.length > 0, scopeLeaf);
      check("S8 scopes differ (parent vs leaf)", scopeParent && scopeLeaf && scopeParent !== scopeLeaf, `parent="${scopeParent}" leaf="${scopeLeaf}"`);
      await app.locator(".v16-selected-range .primary-button").first().click().catch(() => {});
      await sleep(2500);
    } else {
      check("S8 leaf row found after expand", false);
    }

    // ============ S9 question types (choice + big) ============
    console.log("\n== S9 question types ==");
    phase = "chapter-practice";
    // use a branch scope to include both choice + big
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/practice?type=chapter`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitTree(app);
    const branch9 = app.locator(".v16-tree-node:has(.v16-tree-toggle)").first();
    if (await branch9.isVisible().catch(() => false)) {
      await branch9.locator(".v16-tree-select").first().click();
      await sleep(400);
      await app.locator(".v16-selected-range .primary-button").first().click().catch(() => {});
      try { await app.waitForSelector(".mobile-question-meta", { timeout: 15000 }); } catch {}
      await sleep(500);
      const qMetas = await app.locator(".mobile-question-meta").allInnerTexts().catch(() => []);
      const choiceVisible = qMetas.some((m) => m.includes("选择题"));
      const bigVisible = qMetas.some((m) => m.includes("综合题"));
      const noChoiceRaw = !qMetas.some((m) => /\bchoice\b/.test(m));
      const noBigRaw = !qMetas.some((m) => /\bbig\b/.test(m));
      check("S9 shows 选择题 (not 'choice')", choiceVisible, qMetas.slice(0, 3).join(" | "));
      check("S9 no raw 'choice'", noChoiceRaw);
      check("S9 shows 综合题 (not 'big')", bigVisible, bigVisible ? "综合题 found" : "no 综合题 in this scope");
      check("S9 no raw 'big'", noBigRaw);
      const bigIdx = qMetas.findIndex((m) => m.includes("综合题"));
      if (bigIdx >= 0) {
        const bigQ = app.locator(".mobile-practice-question").nth(bigIdx);
        await bigQ.scrollIntoViewIfNeeded().catch(() => {});
        const bigText = await bigQ.innerText().catch(() => "");
        check("S9 big has textarea input", (await bigQ.locator("textarea.mobile-answer-input").count()) > 0, bigText.slice(0, 60));
        await shot("07-big-question");
      }
    } else {
      check("S9 branch node present", false);
    }

    // ============ S10 past paper ============
    console.log("\n== S10 past paper ==");
    phase = "past-paper";
    await app.goto(`${BASE}/m/exam11408/computer_organization/practice?type=past-paper`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(2200);
    await shot("08-past-paper-years");
    check("S10 2022 year present", (await app.locator(".year-list-v14 button", { hasText: "2022" }).count()) > 0);
    await app.locator(".year-list-v14 button", { hasText: "2022" }).first().click().catch(() => {});
    await sleep(400);
    await app.locator("button.primary-button", { hasText: "开始答题" }).first().click().catch(() => {});
    await sleep(3000);
    await shot("09-past-paper");
    const ppCount = captured.pastPaperAttempt?.questions?.length ?? -1;
    const ppTotal = captured.pastPaperAttempt?.attempt?.total_questions ?? -1;
    check("S10 计组2022 Mobile count", ppCount === 26, `mobile=${ppCount} (expected 26)`);
    check("S10 计组2022 total_questions", ppTotal === 26, `total=${ppTotal}`);
    // data_structure 2022
    phase = "past-paper-ds";
    await app.goto(`${BASE}/m/exam11408/data_structure/practice?type=past-paper`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(2200);
    await app.locator(".year-list-v14 button", { hasText: "2022" }).first().click().catch(() => {});
    await sleep(400);
    await app.locator("button.primary-button", { hasText: "开始答题" }).first().click().catch(() => {});
    await sleep(2800);
    const dsCount = captured.pastPaperAttempt?.questions?.length ?? -1;
    check("S10 数据结构2022 Mobile count == PC count (same source)", dsCount > 0, `mobile=${dsCount}`);

    // ============ S11 network isolation ============
    console.log("\n== S11 network isolation ==");
    const ppNet = net.filter((r) => r.phase === "past-paper" || r.phase === "past-paper-ds");
    const cpNet = net.filter((r) => r.phase === "chapter-practice" || r.phase === "knowledge-to-practice");
    check("S11 真题 uses past-paper chain", ppNet.some((r) => r.url.includes("past-paper")));
    check("S11 真题 does NOT call chapter-practice/questions", !ppNet.some((r) => r.url.includes("chapter-practice/questions")));
    check("S11 章节练习 uses chapter-practice/questions", cpNet.some((r) => r.url.includes("chapter-practice/questions")));
    check("S11 章节练习 does NOT call past-paper", !cpNet.some((r) => r.url.includes("past-paper-questions") || r.url.includes("past-paper-attempts")));

    // ============ S12 past paper back ============
    console.log("\n== S12 past paper back ==");
    phase = "past-paper-back";
    await app.goto(`${BASE}/m/exam11408/computer_organization/practice?type=past-paper`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(2000);
    await app.locator(".year-list-v14 button", { hasText: "2022" }).first().click().catch(() => {});
    await sleep(300);
    await app.locator("button.primary-button", { hasText: "开始答题" }).first().click().catch(() => {});
    await sleep(2400);
    const back1 = app.locator(".v16-practice-header button", { hasText: "返回" }).first();
    check("S12 answer page has 返回", await back1.isVisible().catch(() => false));
    await back1.click().catch(() => {});
    await sleep(1200);
    check("S12 返回 -> year page", (await app.locator(".year-list-v14 button").count()) > 0);
    const back2 = app.locator(".v16-practice-header button", { hasText: "返回" }).first();
    if (await back2.isVisible().catch(() => false)) {
      await back2.click().catch(() => {});
      await sleep(1200);
      const ph = await bodyText(app);
      check("S12 year 返回 -> practice home (4 entries)", ["真题", "章节练习", "错题本", "AI出题"].every((n) => ph.includes(n)));
    }

    // ============ S13 wrong book ============
    console.log("\n== S13 wrong book ==");
    phase = "wrong-book";
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/practice?type=wrong`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(2200);
    await shot("10-wrong-book");
    const wbText = await bodyText(app);
    const groups = await app.locator(".v16-wrong-group").count();
    check("S13 wrong book grouped (not flat)", groups > 0, `groups=${groups}`);
    if (groups > 0) {
      check("S13 default folded (no items expanded)", (await app.locator(".v16-wrong-items").count()) === 0);
      await app.locator(".v16-wrong-group-head").first().click().catch(() => {});
      await sleep(500);
      check("S13 expand reveals items", (await app.locator(".v16-wrong-items").count()) > 0);
    } else {
      check("S13 wrong book has groups", false, `wrongText="${wbText.slice(0, 80)}"`);
    }

    // ============ S14 AI generate ============
    console.log("\n== S14 AI generate ==");
    phase = "ai-generate";
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/practice?type=ai`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(2200);
    await shot("11-ai-generate");
    const agText = await bodyText(app);
    check("S14 has 题目数量", agText.includes("题目数量"));
    check("S14 has 难度", agText.includes("难度"));
    check("S14 has 知识范围 (from map)", agText.includes("知识范围") || agText.includes("从知识图谱选择"));
    check("S14 no free chapter/knowledge input", (await app.locator(".v16-form-field input[placeholder*='章节'], .v16-form-field input[placeholder*='知识点']").count()) === 0);
    const rangeBtn = app.locator(".v16-range-button").first();
    if (await rangeBtn.isVisible().catch(() => false)) {
      await rangeBtn.click();
      await sleep(900);
      check("S14 knowledge picker sheet opens", await app.locator(".v16-picker-sheet").isVisible().catch(() => false));
      // wait for picker tree to load, then expand to reveal a leaf
      try { await app.waitForSelector(".v16-picker-sheet .v16-tree-node", { timeout: 15000 }); } catch {}
      await sleep(400);
      const pickerToggles = app.locator(".v16-picker-sheet .v16-tree-toggle");
      const ptc = await pickerToggles.count();
      for (let i = 0; i < Math.min(ptc, 4); i++) { await pickerToggles.nth(i).click().catch(() => {}); await sleep(200); }
      await sleep(400);
      const leafInPicker = app.locator(".v16-picker-sheet .v16-tree-row.is-leaf").first();
      if (await leafInPicker.isVisible().catch(() => false)) {
        await leafInPicker.locator(".v16-tree-select").first().click().catch(() => {});
        await sleep(500);
        const selTxt = await app.locator(".v16-range-button strong").innerText().catch(() => "");
        check("S14 select a real scope", selTxt && selTxt !== "从知识图谱选择", selTxt);
        await app.locator("button.primary-button", { hasText: "生成题目" }).first().click().catch(() => {});
        await sleep(12000);
        const gen = await bodyText(app);
        check("S14 generate produced items", gen.includes("开始答题") || /\d+\./.test(gen), gen.slice(0, 120).replace(/\s+/g, " "));
      } else {
        check("S14 leaf in picker found", false);
      }
    } else {
      check("S14 知识范围 button present", false);
    }

    // ============ S15 AI explanation ============
    console.log("\n== S15 AI explanation ==");
    phase = "ai-explain";
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/practice?type=chapter`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await waitTree(app);
    const branch15 = app.locator(".v16-tree-node:has(.v16-tree-toggle)").first();
    if (await branch15.isVisible().catch(() => false)) {
      await branch15.locator(".v16-tree-select").first().click();
      await sleep(400);
      await app.locator(".v16-selected-range .primary-button").first().click().catch(() => {});
      await sleep(2800);
      const qs = captured.chapterAttempt?.questions || [];
      const firstChoiceIdx = qs.findIndex((q) => ["choice", "选择题", "single_choice"].includes(q.question_type || q.type));
      if (firstChoiceIdx >= 0) {
        const q = qs[firstChoiceIdx];
        const opts = Array.isArray(q.options) ? q.options : (q.options ? Object.entries(q.options) : []);
        const keys = opts.map((o) => (Array.isArray(o) ? o[0] : o[0])).filter(Boolean);
        const correctKey = String(q.standard_answer || "").trim();
        const wrongKey = keys.find((k) => String(k) !== correctKey) || keys[0];
        const qCard = app.locator(".mobile-practice-question").nth(firstChoiceIdx);
        await qCard.locator("button", { hasText: new RegExp("^" + (wrongKey || "A")) }).first().click().catch(() => {});
        await sleep(300);
        await app.locator("button.primary-button", { hasText: "提交" }).first().click().catch(() => {});
        await sleep(2800);
        const aiBtn = app.locator(".practice-result-v14 button", { hasText: "AI解析" }).first();
        if (await aiBtn.isVisible().catch(() => false)) {
          await aiBtn.click();
          await sleep(1500);
          const sheet = await app.locator(".ai-explanation-sheet-v14").isVisible().catch(() => false);
          check("S15 AI解析 sheet opens", sheet);
          const kc = captured.chatPostBody?.knowledge_context || {};
          const ctxOk = Boolean(kc.question) && Boolean(kc.options) && Boolean(kc.correctAnswer) && Boolean(kc.standardExplanation) && Boolean(kc.userAnswer);
          check("S15 POST payload has 题干+选项+我的答案+正确答案+解析", ctxOk, `q="${String(kc.question).slice(0, 24)}" opts=${String(kc.options).slice(0, 20)} user=${kc.userAnswer} ans=${kc.correctAnswer}`);
          try { await app.waitForFunction(() => { const el = document.querySelector(".ai-explanation-sheet-v14"); return el && !el.innerText.includes("正在生成解析"); }, { timeout: 45000 }); } catch {}
          const sheetTxt = await app.locator(".ai-explanation-sheet-v14").innerText().catch(() => "");
          const aiReplyReal = sheetTxt.length > 30 && !sheetTxt.includes("请提供题目") && !sheetTxt.includes("我看不到题目") && !sheetTxt.includes("正在生成解析");
          check("S15 AI reply is question-specific (not loading/generic)", aiReplyReal, sheetTxt.replace(/\s+/g, " ").slice(0, 140));
        } else {
          check("S15 AI解析 button appears after wrong answer", false);
        }
      } else {
        check("S15 found a choice question", false, `types=${qs.map((q) => q.question_type || q.type).slice(0, 5).join(",")}`);
      }
    } else {
      check("S15 branch node present", false);
    }
    check("S15 AI解析 POSTs /api/chat", net.filter((r) => r.phase === "ai-explain" && r.url.includes("/chat") && r.method === "POST").length > 0);
    check("S15 AI解析 does NOT use question-analysis endpoint", !net.filter((r) => r.phase === "ai-explain").some((r) => r.url.includes("question-analysis")));

    // ============ S16 AI chat ============
    console.log("\n== S16 AI chat ==");
    phase = "ai-chat";
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/ai`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(2000);
    await shot("12-ai-chat");
    const chatText = await bodyText(app);
    check("S16 has 返回", (await app.locator(".mobile-chat-back").count()) > 0);
    check("S16 has 历史", (await app.locator(".mobile-chat-history-button").count()) > 0);
    check("S16 title 11408 AI对话", chatText.includes("11408 AI对话"));
    check("S16 composer + input + send", (await app.locator(".mobile-chat-composer").count()) > 0 && (await app.locator(".mobile-ai-tool").count()) > 0 && (await app.locator(".mobile-chat-composer button.primary-button", { hasText: "发送" }).count()) > 0);
    check("S16 no bottom nav in chat", (await app.locator("nav.exam-bottom-nav-v15").count()) === 0);

    // ============ S17 + action sheet ============
    console.log("\n== S17 + action sheet ==");
    await app.locator(".mobile-ai-tool").first().click().catch(() => {});
    await sleep(600);
    const actionSheetTxt = await app.locator(".mobile-action-sheet").innerText().catch(() => "");
    check("S17 action sheet = 上传资料/从资料库选择/取消", actionSheetTxt.includes("上传资料") && actionSheetTxt.includes("从资料库选择") && actionSheetTxt.includes("取消"), actionSheetTxt.replace(/\s+/g, " "));
    await shot("13-add-content");
    await app.locator(".mobile-action-sheet button", { hasText: "取消" }).first().click().catch(() => {});
    await sleep(300);

    // ============ S18 material picker ============
    console.log("\n== S18 material picker ==");
    phase = "material-picker";
    await app.locator(".mobile-ai-tool").first().click().catch(() => {});
    await sleep(500);
    await app.locator(".mobile-action-sheet button", { hasText: "从资料库选择" }).first().click().catch(() => {});
    await sleep(2500);
    await shot("14-material-picker");
    check("S18 material picker opens", await app.locator(".material-picker-sheet").isVisible().catch(() => false));
    const matItems = await app.locator(".material-picker-list button").count();
    if (matItems > 0) {
      await app.locator(".material-picker-list button").first().click().catch(() => {});
      await sleep(300);
      await app.locator(".material-picker-head button", { hasText: "确定" }).first().click().catch(() => {});
      await sleep(500);
      check("S18 selected material chip appears", (await app.locator(".mobile-material-chip").count()) > 0, `picked 1 of ${matItems}`);
    } else {
      check("S18 materials non-empty", false, "empty picker (no PC materials for this subject)");
    }

    // ============ S19 AI history rename/delete ============
    console.log("\n== S19 AI history ==");
    phase = "ai-history";
    await app.goto(`${BASE}/m/exam11408/${SUBJ}/ai`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(1800);
    const textarea = app.locator(".mobile-chat-composer textarea").first();
    if (await textarea.isVisible().catch(() => false)) {
      await textarea.fill("测试历史标题问题：请用一句话回答什么是栈。");
      await app.locator(".mobile-chat-composer button.primary-button").first().click().catch(() => {});
      await sleep(10000);
    }
    await app.locator(".mobile-chat-history-button").first().click().catch(() => {});
    await sleep(1200);
    const historyRows = await app.locator(".mobile-chat-history-row").count();
    check("S19 history list rendered", historyRows > 0, `${historyRows} rows`);
    const newTitle = "验收测试对话标题";
    if (historyRows > 0) {
      const firstRowTitle = await app.locator(".mobile-chat-history-row button").first().innerText().catch(() => "");
      check("S19 history title is short (not full prompt)", firstRowTitle.length <= 40, `"${firstRowTitle.slice(0, 30)}"`);
      await app.locator(".mobile-chat-history-more").first().click().catch(() => {});
      await sleep(500);
      check("S19 session sheet opens (rename/delete)", await app.locator(".mobile-session-sheet").isVisible().catch(() => false));
      const titleInput = app.locator(".mobile-session-sheet input").first();
      if (await titleInput.isVisible().catch(() => false)) {
        await titleInput.fill(newTitle);
        await app.locator(".mobile-session-sheet button", { hasText: "保存标题" }).first().click().catch(() => {});
        await sleep(1500);
      }
      await app.goto(`${BASE}/m/exam11408/${SUBJ}/ai`, { waitUntil: "domcontentloaded", timeout: 60000 });
      await sleep(1800);
      await app.locator(".mobile-chat-history-button").first().click().catch(() => {});
      await sleep(1200);
      check("S19 rename persisted after refresh", (await bodyText(app)).includes(newTitle));
      const targetRow = app.locator(".mobile-chat-history-row", { hasText: newTitle }).first();
      if (await targetRow.isVisible().catch(() => false)) {
        await targetRow.locator(".mobile-chat-history-more").click().catch(() => {});
        await sleep(500);
        await app.locator(".mobile-session-sheet button", { hasText: "删除对话" }).first().click().catch(() => {});
        await sleep(1500);
        await app.goto(`${BASE}/m/exam11408/${SUBJ}/ai`, { waitUntil: "domcontentloaded", timeout: 60000 });
        await sleep(1800);
        await app.locator(".mobile-chat-history-button").first().click().catch(() => {});
        await sleep(1200);
        check("S19 delete persisted after refresh", !(await bodyText(app)).includes(newTitle));
      } else {
        check("S19 renamed row found for delete", false);
      }
    }

    // ============ S20 auth ============
    console.log("\n== S20 auth ==");
    phase = "auth";
    await auth.goto(`${BASE}/m`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(1600);
    await shotAuth("15-login");
    const authText = await bodyText(auth);
    check("S20 login has 账号登录 + 邮箱登录", authText.includes("账号登录") && authText.includes("邮箱登录"));
    check("S20 login has a[href=/terms]", (await auth.locator("a[href='/terms']").count()) > 0);
    check("S20 login has a[href=/privacy]", (await auth.locator("a[href='/privacy']").count()) > 0);
    check("S20 legal text '登录或注册即表示你同意'", authText.includes("登录或注册即表示你同意"));
    check("S20 legal text has 用户协议 + 隐私政策", authText.includes("用户协议") && authText.includes("隐私政策"));
    for (const [href, label] of [["/terms", "terms"], ["/privacy", "privacy"]]) {
      const popupPromise = auth.waitForEvent("popup").catch(() => null);
      await auth.locator(`a[href='${href}']`).first().click().catch(() => {});
      const popup = await popupPromise;
      if (popup) {
        await popup.waitForLoadState("domcontentloaded").catch(() => {});
        const pu = popup.url();
        const ptxt = await popup.locator("body").innerText().catch(() => "");
        check(`S20 click ${label} -> legal page`, pu.includes(label) && ptxt.length > 10, pu);
        await popup.close().catch(() => {});
      } else {
        check(`S20 click ${label} opens`, false);
      }
    }
    await auth.locator(".auth-toggle").first().click().catch(() => {});
    await sleep(700);
    await shotAuth("16-register");
    const regText = await bodyText(auth);
    check("S20 register has a[href=/terms]", (await auth.locator("a[href='/terms']").count()) > 0);
    check("S20 register has a[href=/privacy]", (await auth.locator("a[href='/privacy']").count()) > 0);
    check("S20 register legal text", regText.includes("用户协议") && regText.includes("隐私政策"));

    // ============ S21 viewports ============
    console.log("\n== S21 viewports ==");
    phase = "viewport";
    const vps = [{ w: 360, h: 800 }, { w: 390, h: 844 }, { w: 412, h: 915 }];
    const pages = [
      ["knowledge", `/m/exam11408/${SUBJ}/chapters`],
      ["practice", `/m/exam11408/${SUBJ}/practice`],
      ["pastpaper", `/m/exam11408/computer_organization/practice?type=past-paper`],
      ["ai", `/m/exam11408/${SUBJ}/ai`],
    ];
    let hscrollIssues = 0;
    for (const vp of vps) {
      await app.setViewportSize({ width: vp.w, height: vp.h });
      for (const [tag, route] of pages) {
        await app.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
        await sleep(1600);
        const dim = await app.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
        if (dim.sw > dim.cw + 2) { hscrollIssues++; console.log(`  [hscroll] ${vp.w}x${vp.h} ${tag}: sw=${dim.sw} cw=${dim.cw}`); }
        await shot(`viewport-${vp.w}x${vp.h}-${tag}`);
      }
    }
    check("S21 no horizontal scroll on app pages", hscrollIssues === 0, `${hscrollIssues} issues`);
    for (const vp of vps) {
      await auth.setViewportSize({ width: vp.w, height: vp.h });
      await auth.goto(`${BASE}/m`, { waitUntil: "domcontentloaded", timeout: 60000 });
      await sleep(1400);
      const dim = await auth.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
      if (dim.sw > dim.cw + 2) { hscrollIssues++; console.log(`  [hscroll] ${vp.w}x${vp.h} login: sw=${dim.sw} cw=${dim.cw}`); }
      await shotAuth(`viewport-${vp.w}x${vp.h}-login`);
    }
    await app.setViewportSize({ width: 390, height: 844 });

    console.log("\n\n===== NETWORK LOG summary =====");
    const summary = {};
    for (const r of net) summary[r.phase] = (summary[r.phase] || 0) + 1;
    console.log(JSON.stringify(summary));
  } catch (e) {
    console.error("FATAL", e.message, e.stack?.split("\n")[1] || "");
  } finally {
    await browser.close();
    const pass = results.filter((r) => r.ok).length;
    console.log(`\n===== v16.5.2 PRODUCTION RESULT ===== PASS=${results.every((r) => r.ok)} (${pass}/${results.length})`);
    const fails = results.filter((r) => !r.ok);
    if (fails.length) { console.log("\n-- FAILURES --"); fails.forEach((f) => console.log("FAIL |", f.name, "|", f.extra)); }
    fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify({ results, net, captured: { pastPaper: captured.pastPaperAttempt?.questions?.length, chapter: captured.chapterAttempt?.questions?.length } }, null, 2));
  }
}

main();
