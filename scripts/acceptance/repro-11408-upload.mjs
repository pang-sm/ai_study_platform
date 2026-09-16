import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const AUTH = path.join(PROJECT_ROOT, ".playwright", ".auth", "stage4-materials-relogin-production.json");
const BASE = "https://101.32.190.42";
const TEST_FILE = "C:/Users/26477/Desktop/课程文件/大二上/计组/coa26_书面作业01.pdf";

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ storageState: AUTH, viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
const log = [];

page.on("request", (req) => {
  const u = req.url();
  if (u.includes("/api/materials")) {
    log.push({ kind: "REQ", method: req.method(), url: u, contentType: req.headers()["content-type"] || "" });
  }
});
page.on("response", async (res) => {
  const u = res.url();
  if (u.includes("/api/materials")) {
    try {
      const j = await res.json();
      if (u.includes("/upload")) {
        log.push({ kind: "UPLOAD-RESP", status: res.status(), material_id: j?.material_id, course_id: j?.material?.course_id, subject_key: j?.material?.subject_key, subject: j?.material?.subject, fn: j?.material?.file_name, detail: j?.detail });
      } else {
        const ids = (j?.materials || []).map(m => m.id);
        log.push({ kind: "LIST-RESP", status: res.status(), url: u, count: (j?.materials || []).length, ids, names: (j?.materials || []).map(m => m.file_name || m.original_filename) });
      }
    } catch {}
  }
});

const body = () => page.evaluate(() => document.body.innerText);

// switch to exam
await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: 60000 });
await page.waitForTimeout(3200);
if (await page.getByRole("button", { name: "个人主页" }).first().isVisible().catch(() => false)) {
  await page.getByRole("button", { name: "个人主页" }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2200);
  await page.getByText("切换到 11408", { exact: false }).first().click({ timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3800);
}
// enter 计组
await page.locator(".eh-subject-tile", { hasText: "计算机组成原理" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(2800);
// 资料库
await page.getByRole("button", { name: "资料库" }).first().click({ timeout: 15000 }).catch(() => {});
await page.waitForTimeout(3500);
console.log("MATERIALS URL:", page.url());
const before = await page.evaluate(() => Array.from(document.querySelectorAll("tbody tr td:first-child")).map(t => t.innerText.trim()).filter(Boolean));
console.log("BEFORE files:", JSON.stringify(before));

// upload the real file
await page.locator("input[type=file]").first().setInputFiles(TEST_FILE).catch((e) => console.log("upload err", e.message));
await page.waitForTimeout(6000);
console.log("AFTER upload URL:", page.url());
const after = await page.evaluate(() => Array.from(document.querySelectorAll("tbody tr td:first-child")).map(t => t.innerText.trim()).filter(Boolean));
console.log("AFTER files:", JSON.stringify(after));

console.log("\n===== NETWORK LOG =====");
for (const l of log) console.log(JSON.stringify(l));
await browser.close();
