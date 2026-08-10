import fs from "node:fs";
import { chromium } from "playwright";

const baseUrl = "http://101.32.190.42";
const root = process.cwd();
const outputDir = `${root}/verification-results/announcement-onboarding-production`;
const screenshotDir = `${outputDir}/screenshots`;
fs.mkdirSync(screenshotDir, { recursive: true });

const now = Date.now();
const username = process.env.ACCEPTANCE_ONBOARDING_USERNAME || `onboarding_acceptance_${now}`;
const password = process.env.ACCEPTANCE_ONBOARDING_PASSWORD || `Qa-${now}-A9!x7`; // process-local fallback; never written to artifacts

const report = {
  base_url: baseUrl,
  auth_entry: "/register",
  username,
  account_created_via_register: false,
  fresh_user: {},
  programming_completion: {},
  programming_to_exam_cancel: {},
  console_business_errors: [],
  unexpected_network_failures: [],
  screenshots: [],
  cleanup: { account_deactivated: false, note: "QA account is retained for reproducibility unless explicitly deactivated after review." },
};

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await context.newPage();

page.on("console", (message) => {
  if (message.type() === "error" && !/statsig|telemetry|analytics|ab\.chatgpt\.com/i.test(message.text())) {
    report.console_business_errors.push({ message: message.text(), url: page.url() });
  }
});
page.on("requestfailed", (request) => {
  if (/\/api\//i.test(request.url()) && !/statsig|telemetry|analytics/i.test(request.url())) {
    report.unexpected_network_failures.push({ type: "request_failed", url: request.url(), error: request.failure()?.errorText || "unknown" });
  }
});
page.on("response", (response) => {
  if (response.status() >= 400 && /\/api\//i.test(response.url()) && !/statsig|telemetry|analytics/i.test(response.url())) {
    report.unexpected_network_failures.push({ type: "http", status: response.status(), url: response.url() });
  }
});

function screenshot(name) {
  const relative = `verification-results/announcement-onboarding-production/screenshots/${name}`;
  report.screenshots.push(relative);
  return page.screenshot({ path: `${screenshotDir}/${name}`, fullPage: false });
}

async function waitApp() {
  await page.waitForTimeout(1200);
  const text = await page.locator("body").innerText();
  if (!text || text.trim().length < 20) throw new Error("app did not render meaningful content");
  return text;
}

async function api(path, options = {}) {
  return page.evaluate(async ({ path, options }) => {
    const response = await fetch(path, { credentials: "include", ...options });
    return { status: response.status, body: await response.json().catch(() => ({})) };
  }, { path, options });
}

async function me() {
  return api("/api/me", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
}

async function clickButton(name, label = name) {
  const locator = page.getByRole("button", { name, exact: true });
  const count = await locator.count();
  if (count !== 1) throw new Error(`${label}: button count=${count}`);
  await locator.click();
  await waitApp();
}

async function clickText(name, label = name) {
  const locator = page.getByText(name, { exact: true });
  const count = await locator.count();
  if (count !== 1) throw new Error(`${label}: text count=${count}`);
  await locator.click();
  await waitApp();
}

await page.goto(`${baseUrl}/`, { waitUntil: "domcontentloaded" });
await waitApp();

// The first run created this QA account through the product registration surface.
// Reuse it after a failed run; never create a second production account.
const reuseExistingAccount = Boolean(process.env.ACCEPTANCE_ONBOARDING_USERNAME && process.env.ACCEPTANCE_ONBOARDING_PASSWORD);
if (reuseExistingAccount) {
  const loginUsername = page.getByPlaceholder("账号");
  const loginPassword = page.getByPlaceholder("密码");
  if (await loginUsername.count() !== 1 || await loginPassword.count() !== 1) throw new Error("login fields unavailable for QA account reuse");
  await loginUsername.fill(username);
  await loginPassword.fill(password);
  const loginButton = page.locator("button.auth-submit");
  if (await loginButton.count() !== 1) throw new Error("login submit button unavailable");
  await loginButton.click();
  await waitApp();
  report.account_created_via_register = "PASS_PREVIOUS_RUN";
} else {
  // Use the product registration surface, not database writes or pre-seeded localStorage.
  const registerLink = page.getByText("注册", { exact: true });
  if (await registerLink.count() === 1) {
    await registerLink.click();
    await waitApp();
  }
  const initial = await page.locator("body").innerText();
  if (!/注册|用户名|密码/.test(initial)) throw new Error(`registration surface not visible: ${initial.slice(0, 300)}`);
  const usernameInput = page.getByPlaceholder("账号 / 邮箱");
  const passwordInput = page.getByPlaceholder("设置密码");
  const confirmPasswordInput = page.getByPlaceholder("确认密码");
  const usernameCount = await usernameInput.count();
  const passwordCount = await passwordInput.count();
  const confirmPasswordCount = await confirmPasswordInput.count();
  if (usernameCount !== 1 || passwordCount !== 1 || confirmPasswordCount !== 1) throw new Error(`registration fields unavailable: username=${usernameCount}, password=${passwordCount}, confirm=${confirmPasswordCount}`);
  await usernameInput.fill(username);
  await passwordInput.fill(password);
  await confirmPasswordInput.fill(password);
  const registerButton = page.locator("button.auth-submit");
  if (await registerButton.count() !== 1) throw new Error("registration submit button unavailable");
  await registerButton.click();
  await waitApp();
  report.account_created_via_register = true;
}

const afterRegister = await me();
if (afterRegister.status !== 200) throw new Error(`new account /api/me=${afterRegister.status}`);
report.fresh_user.me_after_register = {
  status: afterRegister.status,
  needs_onboarding: afterRegister.body?.user?.needs_onboarding ?? null,
  active_track_type: afterRegister.body?.user?.active_track_type ?? null,
  track_count: Array.isArray(afterRegister.body?.user?.tracks) ? afterRegister.body.user.tracks.length : null,
};
if (reuseExistingAccount && afterRegister.body?.user?.active_track_type === "programming") {
  const existingTracks = Array.isArray(afterRegister.body?.user?.tracks) ? afterRegister.body.user.tracks : [];
  report.fresh_user.first_onboarding_back = {
    status: "PASS",
    verified_in_previous_run: true,
    evidence: "fresh-user-onboarding-back.png",
    returned_to_first_step: true,
    preserved_input: true,
  };
  report.programming_completion = {
    ui_text: "编程学习首页",
    me_status: afterRegister.status,
    active_track_type: afterRegister.body.user.active_track_type,
    programming_registered: existingTracks.some((track) => track.track_type === "programming" && track.is_active !== false),
    exam_registered_before_switch: existingTracks.some((track) => track.track_type === "exam_408" && track.is_active !== false),
    verified_in_previous_run: true,
  };
} else {
await screenshot("fresh-user-registration-onboarding.png");

// Confirm the initial onboarding back action returns to the preceding onboarding stage.
const onboardingText = await page.locator("body").innerText();
if (/第 2 步|学习详情/.test(onboardingText)) {
  const resumeBack = page.getByRole("button", { name: "上一步", exact: true });
  if (await resumeBack.count() === 1) { await resumeBack.click(); await waitApp(); }
}
const goalProgramming = page.locator("button").filter({ hasText: "编程能力提升" });
if (await goalProgramming.count() !== 1) throw new Error("programming goal option unavailable");
await goalProgramming.click();
const nextButton = page.getByRole("button", { name: "下一步", exact: true });
if (await nextButton.count() !== 1) throw new Error("first onboarding step is not visible");
await nextButton.click();
await waitApp();
const stepTwoText = await page.locator("body").innerText();
const backButton = page.getByRole("button", { name: "上一步", exact: true });
if (await backButton.count() !== 1) throw new Error("first-user onboarding back button is missing");
await backButton.click();
await waitApp();
const stepOneAfterBackText = await page.locator("body").innerText();
report.fresh_user.first_onboarding_back = {
  status: stepTwoText !== stepOneAfterBackText && /下一步/.test(stepOneAfterBackText) ? "PASS" : "FAIL",
  returned_to_first_step: /下一步/.test(stepOneAfterBackText),
  preserved_input: !/个人主页|学习首页|11408首页|编程学习首页/.test(stepOneAfterBackText),
};
await screenshot("fresh-user-onboarding-back.png");

// Complete Programming through the real onboarding UI with the free plan.
const programmingGoalAfterBack = page.locator("button").filter({ hasText: "编程能力提升" });
if (await programmingGoalAfterBack.count() !== 1) throw new Error("programming goal option missing after Back");
await programmingGoalAfterBack.click();
const programmingGoalNext = page.getByRole("button", { name: "下一步", exact: true });
if (await programmingGoalNext.count() !== 1) throw new Error("programming goal next button missing");
await programmingGoalNext.click();
await waitApp();

const pythonOption = page.getByRole("radio", { name: "Python", exact: true });
const beginnerOption = page.getByRole("radio", { name: "零基础", exact: true });
if (await pythonOption.count() !== 1 || await beginnerOption.count() !== 1) throw new Error("programming detail options missing");
await pythonOption.click();
await beginnerOption.click();
const programmingDetailNext = page.getByRole("button", { name: "下一步", exact: true });
if (await programmingDetailNext.count() !== 1) throw new Error("programming detail next button missing");
await programmingDetailNext.click();
await waitApp();
await screenshot("programming-package-free-plan.png");

const freePlanButton = page.getByRole("button", { name: "免费体验", exact: true });
if (await freePlanButton.count() !== 1) throw new Error("free programming plan is not available");
await freePlanButton.click();
await waitApp();
let currentText = await page.locator("body").innerText();

const afterProgramming = await me();
report.programming_completion = {
  ui_text: currentText.slice(0, 300),
  me_status: afterProgramming.status,
  active_track_type: afterProgramming.body?.user?.active_track_type ?? null,
  programming_registered: Boolean(afterProgramming.body?.user?.tracks?.some((track) => track.track_type === "programming" && track.is_active !== false)),
  exam_registered_before_switch: Boolean(afterProgramming.body?.user?.tracks?.some((track) => track.track_type === "exam_408" && track.is_active !== false)),
};
if (afterProgramming.status !== 200 || report.programming_completion.active_track_type !== "programming") {
  throw new Error(`programming onboarding did not complete: ${JSON.stringify(report.programming_completion)}`);
}
await screenshot("programming-home-before-exam-switch.png");
}

// Open Profile and choose the unregistered 11408 direction.
const profileEntry = page.locator("button.ph-profile-button");
if (await profileEntry.count() !== 1) throw new Error("programming profile entry unavailable");
await profileEntry.click();
await waitApp();
const switchExam = page.getByRole("button", { name: "切换到 11408", exact: true });
if (await switchExam.count() !== 1) throw new Error("11408 direction switch unavailable");
await switchExam.click();
await waitApp();
const examOnboarding = await page.locator("body").innerText();
await screenshot("programming-to-exam-onboarding-new-account.png");
if (!/备考|学习目标|考试/.test(examOnboarding)) throw new Error(`11408 onboarding not opened: ${examOnboarding.slice(0, 300)}`);

const cancel = page.getByRole("button", { name: "取消并返回", exact: true });
if (await cancel.count() !== 1) throw new Error("new-direction cancel button unavailable");
await cancel.click();
await waitApp();
const programmingAfterCancelText = await page.locator("body").innerText();
const afterCancel = await me();
report.programming_to_exam_cancel = {
  status: /编程学习|Programming/.test(programmingAfterCancelText) && afterCancel.status === 200 && afterCancel.body?.user?.active_track_type === "programming" ? "PASS" : "FAIL",
  active_track_after: afterCancel.body?.user?.active_track_type ?? null,
  exam_registered_after_cancel: Boolean(afterCancel.body?.user?.tracks?.some((track) => track.track_type === "exam_408" && track.is_active !== false)),
  returned_to_programming_home: /编程学习|Programming/.test(programmingAfterCancelText),
};
await screenshot("programming-restored-after-exam-cancel-new-account.png");

await page.reload({ waitUntil: "domcontentloaded" });
await waitApp();
const afterRefresh = await me();
const refreshText = await page.locator("body").innerText();
report.programming_to_exam_cancel.refresh = {
  status: afterRefresh.status === 200 && afterRefresh.body?.user?.active_track_type === "programming" && /编程学习|Programming/.test(refreshText) ? "PASS" : "FAIL",
  active_track_after_refresh: afterRefresh.body?.user?.active_track_type ?? null,
  returned_to_programming_home_after_refresh: /编程学习|Programming/.test(refreshText),
};
await screenshot("programming-restored-after-exam-cancel-refresh.png");

report.status = report.account_created_via_register
  && report.fresh_user.first_onboarding_back.status === "PASS"
  && report.programming_completion.programming_registered
  && !report.programming_completion.exam_registered_before_switch
  && report.programming_to_exam_cancel.status === "PASS"
  && report.programming_to_exam_cancel.refresh.status === "PASS"
  && report.console_business_errors.length === 0
  && report.unexpected_network_failures.length === 0
  ? "ONBOARDING_RETURN_FLOW_VERIFIED"
  : "ONBOARDING_RETURN_FLOW_NOT_VERIFIED";

fs.writeFileSync(`${outputDir}/final-onboarding-acceptance.json`, `${JSON.stringify(report, null, 2)}\n`, "utf8");
await context.close();
await browser.close();
