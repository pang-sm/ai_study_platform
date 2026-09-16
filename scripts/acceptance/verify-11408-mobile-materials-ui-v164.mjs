// P0-A UI smoke: confirm the mobile "+" opens an action sheet (not a file dialog),
// the library picker lists real materials, and selection renders a removable chip.
import { chromium } from "playwright";

const WEB = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000";
const USER = `mobile_v164_ui_${Date.now()}`;
const PASS = "v164test123";
const SUBJECT_KEY = "computer_organization";
const COURSE_ID = `${SUBJECT_KEY}_11408`;
const SUBJECT = "11408 计算机组成原理";

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
const api = ctx.request;
const results = [];
const check = (name, ok) => { results.push([name, ok]); console.log(`${ok ? "PASS" : "FAIL"} ${name}`); };

try {
  await api.post(`${API}/register`, { data: { username: USER, password: PASS } });
  // upload one real material so the picker has content
  const up = await api.post(`${API}/materials/upload`, {
    multipart: {
      file: { name: "mobile-v164-material.txt", mimeType: "text/plain", buffer: Buffer.from("MOBILE_V164_SECRET = 271828\n") },
      username: USER, course_id: COURSE_ID, subject_key: SUBJECT_KEY, subject: SUBJECT,
      track: "exam_11408", save_to_materials: "true", source_type: "user_upload",
    },
  });
  console.log(`upload status=${up.status()}`);

  const page = await ctx.newPage();
  await page.goto(`${WEB}/m`, { waitUntil: "domcontentloaded", timeout: 60000 });
  // seed localStorage so the SPA skips auth/onboarding (cookie is already set by register)
  await page.evaluate((u) => localStorage.setItem("ai_study_platform_user", JSON.stringify({ username: u, nickname: "V164测试" })), USER);

  await page.goto(`${WEB}/m/exam11408/${SUBJECT_KEY}/ai`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(2500);

  // 1. "+" must open the action sheet, not trigger a file chooser
  const plusBtn = page.locator(".mobile-ai-tool").first();
  const fileChooser = page.waitForEvent("filechooser", { timeout: 2000 }).then(() => true).catch(() => false);
  await plusBtn.click();
  await page.waitForTimeout(600);
  const sheetVisible = await page.locator(".mobile-action-sheet", { hasText: "添加内容" }).isVisible().catch(() => false);
  const chooserOpened = await fileChooser;
  check("'+' opens action sheet (not file chooser)", sheetVisible && !chooserOpened);
  check("sheet shows '上传资料' + '从资料库选择'", (await page.getByText("上传资料").first().isVisible().catch(() => false)) && (await page.getByText("从资料库选择").first().isVisible().catch(() => false)));

  // 2. '从资料库选择' opens the picker listing the uploaded material
  await page.getByText("从资料库选择").first().click();
  await page.waitForTimeout(1500);
  const pickerVisible = await page.locator(".material-picker-sheet").isVisible().catch(() => false);
  const pickerListsFile = await page.locator(".material-picker-list", { hasText: "mobile-v164-material.txt" }).isVisible().catch(() => false);
  check("library picker opens and lists uploaded material", pickerVisible && pickerListsFile);

  // 3. selecting renders a removable chip
  await page.locator(".material-picker-list > button").first().click();
  await page.waitForTimeout(300);
  await page.locator(".material-picker-head button", { hasText: "确定" }).click();
  await page.waitForTimeout(500);
  const chipVisible = await page.locator(".mobile-material-chip", { hasText: "mobile-v164-material.txt" }).isVisible().catch(() => false);
  check("selected material renders a chip", chipVisible);

  // 4. send a message through the UI and confirm the answer carries the RAG secret
  await page.locator(".mobile-chat-composer textarea").fill("MOBILE_V164_SECRET 的值是什么？");
  await page.locator(".mobile-chat-composer button[type=submit]").click();
  let answered = false;
  for (let i = 0; i < 30; i++) {
    await page.waitForTimeout(1500);
    const bodyText = await page.evaluate(() => document.body.innerText);
    if (bodyText.includes("271828")) { answered = true; break; }
  }
  check("UI chat answers 271828 via selected material", answered);

  await page.screenshot({ path: "verification-results/mobile-v164-material-chat.png" }).catch(() => {});
} catch (e) {
  console.error("FATAL", e.message);
} finally {
  await browser.close();
  const allPass = results.every(([, ok]) => ok);
  console.log(`\n===== UI RESULT =====  PASS=${allPass}  (${results.filter(([, ok]) => ok).length}/${results.length})`);
  console.log(`TEST_USER=${USER}`);
}
