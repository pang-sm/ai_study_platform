// v16.5 visual rewrite — capture all 13 screenshots at 3 viewports.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WEB = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000";
const SUBJECT = "computer_organization";
const USER = `mobile_v165_vis_${Date.now()}`;
const PASS = "v165vis123";
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../verification-results/mobile-v165");
fs.mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [{ w: 390, h: 844, tag: "390x844" }, { w: 360, h: 800, tag: "360x800" }, { w: 412, h: 915, tag: "412x915" }];

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const api = ctx.request;
try {
  await api.post(`${API}/register`, { data: { username: USER, password: PASS } });
  // upload one material so material picker has content
  await api.post(`${API}/materials/upload`, {
    multipart: {
      file: { name: "mobile-v165-ref.txt", mimeType: "text/plain", buffer: Buffer.from("V165 REF = 1\n") },
      username: USER, course_id: `${SUBJECT}_11408`, subject_key: SUBJECT, subject: "11408 计算机组成原理",
      track: "exam_11408", save_to_materials: "true", source_type: "user_upload",
    },
  });
  const page = await ctx.newPage();
  await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.evaluate((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify({ username: u, nickname: "V165", onboarding_completed: true })), USER);

  const shoot = async (name, route, opts = {}) => {
    await page.goto(`${WEB}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(opts.wait || 1800);
    if (opts.actions) await opts.actions(page);
    await page.waitForTimeout(opts.wait2 || 300);
    await page.screenshot({ path: path.join(OUT, name) }).catch(() => {});
    console.log("shot", name);
  };

  // main viewport 390x844 — all 13
  await shoot("01-subject-select.png", "/m/exam11408", { wait: 1500 });
  await shoot("02-knowledge-collapsed.png", `/m/exam11408/${SUBJECT}/chapters`, { wait: 2200 });
  await shoot("03-knowledge-expanded.png", `/m/exam11408/${SUBJECT}/chapters`, { wait: 2200, actions: async (p) => { const t = p.locator(".v16-tree-toggle").first(); if (await t.isVisible().catch(() => false)) await t.click(); } });
  await shoot("04-practice-home.png", `/m/exam11408/${SUBJECT}/practice`, { wait: 1600 });
  await shoot("05-chapter-practice.png", `/m/exam11408/${SUBJECT}/practice?type=chapter`, { wait: 2200 });
  await shoot("06-chapter-question-choice.png", `/m/exam11408/${SUBJECT}/practice?type=chapter&knowledgeId=1.1&knowledge=%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%B3%BB%E7%BB%9F%E6%A6%82%E8%BF%B0`, { wait: 2000, actions: async (p) => { await p.locator(".v16-selected-range .primary-button").first().click(); }, wait2: 2500 });
  await shoot("07-chapter-question-big.png", `/m/exam11408/${SUBJECT}/practice?type=chapter&knowledgeId=1.1&knowledge=%E8%AE%A1%E7%AE%97%E6%9C%BA%E7%B3%BB%E7%BB%9F%E6%A6%82%E8%BF%B0`, { wait: 2000, actions: async (p) => { await p.locator(".v16-selected-range .primary-button").first().click(); }, wait2: 2500, actions2: async (p) => { const big = p.locator(".mobile-question-meta", { hasText: "综合题" }).first(); if (await big.isVisible().catch(() => false)) await big.scrollIntoViewIfNeeded(); } });
  await shoot("08-past-paper-years.png", `/m/exam11408/${SUBJECT}/practice?type=past-paper`, { wait: 2000 });
  await shoot("09-past-paper-question.png", `/m/exam11408/${SUBJECT}/practice?type=past-paper`, { wait: 2000, actions: async (p) => { const y = p.locator(".year-list-v14 button", { hasText: "2022" }).first(); if (await y.isVisible().catch(() => false)) await y.click(); await p.locator("button.primary-button", { hasText: "开始答题" }).first().click(); }, wait2: 2500 });
  await shoot("10-wrong-book.png", `/m/exam11408/${SUBJECT}/practice?type=wrong`, { wait: 2000 });
  await shoot("11-ai-generate.png", `/m/exam11408/${SUBJECT}/practice?type=ai`, { wait: 2000 });
  await shoot("12-ai-chat.png", `/m/exam11408/${SUBJECT}/ai`, { wait: 2000 });
  await shoot("13-material-picker.png", `/m/exam11408/${SUBJECT}/ai`, { wait: 2000, actions: async (p) => { await p.locator(".mobile-ai-tool").first().click(); await p.waitForTimeout(400); await p.getByText("从资料库选择").first().click(); }, wait2: 1500 });

  // 3 viewports for key pages
  for (const vp of VIEWPORTS.slice(1)) {
    await page.setViewportSize({ width: vp.w, height: vp.h });
    await shoot(`viewport-${vp.tag}-knowledge.png`, `/m/exam11408/${SUBJECT}/chapters`, { wait: 2000 });
    await shoot(`viewport-${vp.tag}-practice-home.png`, `/m/exam11408/${SUBJECT}/practice`, { wait: 1600 });
    await shoot(`viewport-${vp.tag}-subject-select.png`, `/m/exam11408`, { wait: 1500 });
  }
} catch (e) {
  console.error("FATAL", e.message);
} finally {
  await browser.close();
  console.log("\n===== SCREENSHOTS DONE =====");
  console.log(`TEST_USER=${USER}`);
  const files = fs.readdirSync(OUT);
  console.log(`count=${files.length}`);
  console.log(files.join("\n"));
}
