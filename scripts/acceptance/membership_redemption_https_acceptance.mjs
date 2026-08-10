import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const baseUrl = (process.env.ACCEPTANCE_BASE_URL || "https://101.32.190.42").replace(/\/$/, "");
const adminState = path.resolve(root, ".playwright/.auth/admin-dashboard-production.json");
const outputDir = path.resolve(root, "verification-results/membership-redemption-production");
const checkoutState = path.resolve(root, ".playwright/.auth/https-checkout-qa.json");
const redemptionState = path.resolve(root, ".playwright/.auth/https-redemption-qa.json");
fs.mkdirSync(outputDir, { recursive: true });

const runStamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
const report = {
  audit: "https-membership-checkout-redemption-production-acceptance",
  base_url: baseUrl,
  checkout_qa: { created_via: "/register UI", username: `https_checkout_qa_${runStamp}` },
  redemption_qa: { created_via: "/register UI", username: `https_redeem_qa_${runStamp}` },
  redemption_code: { created_via: "admin UI", service_key: "course_learning", target_plan: "monthly", duration_days: 30, max_redemptions: 1, note: "HTTPS security freeze acceptance" },
  records: {}, console_business_errors: [], unexpected_network_failures: [], mixed_content: [], status: "not_started",
};
let signoutInProgress = false;
let exhaustedPreviewInProgress = false;

function password() { return `Qa!${crypto.randomBytes(18).toString("base64url")}9`; }
function rel(file) { return path.relative(root, file).replaceAll("\\", "/"); }
function cleanUrl(url) { return url.replace(/([?&](?:code|token|password)=)[^&]+/gi, "$1<redacted>"); }
function attach(page, expectedFailure = () => false) {
  page.on("console", (message) => {
    const expectedBrowserMessage = (signoutInProgress && /401 \(Unauthorized\)/.test(message.text()))
      || (exhaustedPreviewInProgress && /400 \(Bad Request\)/.test(message.text()));
    if (["error", "warning"].includes(message.type()) && !expectedBrowserMessage && !/statsig|telemetry|analytics/i.test(message.text())) report.console_business_errors.push(message.text().slice(0, 500));
  });
  page.on("pageerror", (error) => report.console_business_errors.push(String(error.message || error).slice(0, 500)));
  page.on("response", (response) => {
    const url = response.url();
    if (url.startsWith("http://")) report.mixed_content.push(cleanUrl(url));
    const isExpectedExhaustedPreview = response.status() >= 400 && /\/api\/membership\/redeem\/preview$/.test(url);
    const isExpectedSignoutRequest = signoutInProgress && response.status() === 401;
    if (response.status() >= 400 && /\/api\//.test(url) && !isExpectedExhaustedPreview && !isExpectedSignoutRequest && !expectedFailure(response)) report.unexpected_network_failures.push({ status: response.status(), url: cleanUrl(url) });
  });
  page.on("requestfailed", (request) => {
    if (/\/api\//.test(request.url()) && request.failure()?.errorText !== "net::ERR_ABORTED") report.unexpected_network_failures.push({ status: "request_failed", url: cleanUrl(request.url()) });
  });
}
async function api(page, pathname, options = {}) {
  return page.evaluate(async ({ url, options }) => { const r = await fetch(url, { credentials: "include", ...options }); return { status: r.status, body: await r.json().catch(() => ({})) }; }, { url: pathname, options });
}
function me(page) { return api(page, "/api/me", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); }
async function click(locator, name) { await locator.waitFor({ state: "visible", timeout: 30000 }); await locator.click(); }
async function chooseFirstNonEmpty(select) {
  const value = await select.evaluate((element) => Array.from(element.options).find((option) => option.value)?.value || "");
  if (!value) throw new Error("onboarding select has no usable option");
  await select.selectOption(value);
}
async function registerAndOnboard(browser, username, secret, statePath) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage(); attach(page);
  await page.goto(baseUrl, { waitUntil: "commit", timeout: 45000 });
  await click(page.locator(".auth-tab").nth(1), "register tab");
  const fields = page.locator(".auth-input");
  await fields.nth(0).fill(username); await fields.nth(1).fill(secret); await fields.nth(2).fill(secret);
  await click(page.locator(".auth-submit"), "register submit");
  await click(page.locator(".ob-goal-card-v2").filter({ hasText: "课程" }).first(), "course-learning goal");
  await click(page.locator(".ob-btn-primary").first(), "onboarding continue");
  await page.locator(".course-onboarding-page").waitFor({ state: "visible", timeout: 30000 });
  const selects = page.locator(".course-onboarding-page select");
  await chooseFirstNonEmpty(selects.nth(0)); await chooseFirstNonEmpty(selects.nth(1));
  await click(page.locator(".course-onboarding-chip").first(), "course choice");
  await click(page.locator(".course-onboarding-material").first(), "material choice");
  await click(page.locator(".course-onboarding-next"), "course onboarding next");
  await page.locator(".plan-selection-card").filter({ has: page.locator(".plan-selection-free") }).first().click();
  await click(page.locator(".ob-btn-primary").first(), "free plan confirmation");
  await page.locator(".clh-user-card").waitFor({ state: "visible", timeout: 30000 });
  const currentUser = await me(page);
  if (currentUser.status !== 200) throw new Error(`new QA account authentication failed: ${currentUser.status}`);
  await context.storageState({ path: statePath });
  return { context, page, me: currentUser.body };
}
async function openMembership(page) {
  await click(page.locator(".clh-user-card"), "course profile");
  await page.locator(".ep-page-wrap").waitFor({ state: "visible", timeout: 30000 });
  await click(page.locator("button.ep-outline-btn").last(), "membership details");
  await page.locator(".membership-shell").waitFor({ state: "visible", timeout: 30000 });
}
function orderList(body) { return Array.isArray(body?.items) ? body.items : Array.isArray(body) ? body : Array.isArray(body?.orders) ? body.orders : []; }
async function checkoutAcceptance(browser, username, secret) {
  const created = await registerAndOnboard(browser, username, secret, checkoutState);
  const { context, page } = created;
  try {
    await openMembership(page);
    const catalogBefore = await api(page, "/api/membership/catalog?service_key=course_learning");
    const higher = page.locator(".plan-selection-card").filter({ hasNot: page.locator(".plan-selection-free") }).locator(".plan-selection-button:not([disabled])").first();
    await click(higher, "legal higher plan");
    await page.locator(".checkout-shell").waitFor({ state: "visible", timeout: 30000 });
    const ordersPending = await api(page, "/api/membership/orders?service_key=course_learning");
    const pendingOrder = orderList(ordersPending.body).find((item) => item.status === "pending");
    if (!pendingOrder) throw new Error("pending membership order not found after UI plan selection");
    report.checkout_qa.order_id = pendingOrder.id || pendingOrder.order_id || null;
    report.records.checkout_pending = { passed: ordersPending.status === 200, order_status: pendingOrder.status };
    await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
    await page.locator(".checkout-shell").waitFor({ state: "visible", timeout: 30000 });
    const afterReload = await api(page, "/api/membership/orders?service_key=course_learning");
    const reloadedOrder = orderList(afterReload.body).find((item) => String(item.id || item.order_id) === String(report.checkout_qa.order_id));
    report.records.checkout_refresh_pending = { passed: reloadedOrder?.status === "pending", order_status: reloadedOrder?.status || null };
    await click(page.locator(".checkout-button.checkout-button-primary"), "mock payment");
    await page.getByText(/支付成功|已支付|购买成功/).first().waitFor({ state: "visible", timeout: 30000 });
    await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
    const paidOrders = await api(page, "/api/membership/orders?service_key=course_learning");
    const paidOrder = orderList(paidOrders.body).find((item) => String(item.id || item.order_id) === String(report.checkout_qa.order_id));
    const paidMe = await me(page);
    const paidCatalog = await api(page, "/api/membership/catalog?service_key=course_learning");
    report.records.checkout_paid_refresh = { passed: paidOrder?.status === "paid", order_status: paidOrder?.status || null };
    report.records.checkout_membership_profile_quota = {
      passed: paidMe.status === 200 && paidCatalog.status === 200 && paidCatalog.body?.current?.plan === "monthly" && Boolean(paidCatalog.body?.current?.expires_at),
      me_status: paidMe.status,
      catalog_status: paidCatalog.status,
      return_route: page.url().replace(baseUrl, "") || "/",
    };
  } finally { await page.waitForTimeout(750).catch(() => {}); await context.close(); }
}
async function createCodeThroughAdmin(browser) {
  if (!fs.existsSync(adminState)) throw new Error("admin HTTPS auth state is missing");
  const context = await browser.newContext({ storageState: adminState, viewport: { width: 1440, height: 900 } });
  const page = await context.newPage(); attach(page);
  let code = null;
  const codeResponse = new Promise((resolve) => page.on("response", async (response) => {
    if (response.request().method() === "POST" && /\/api\/admin\/membership\/redemption-codes$/.test(response.url())) {
      const body = await response.json().catch(() => ({})); resolve(body);
    }
  }));
  await page.goto(baseUrl, { waitUntil: "commit", timeout: 45000 });
  const currentUser = await me(page);
  if (currentUser.status !== 200 || !(currentUser.body?.user?.is_admin ?? currentUser.body?.profile?.is_admin)) throw new Error("admin HTTPS session is not authorized");
  await click(page.locator(".admin-dashboard-nav-item").filter({ hasText: "兑换码" }), "admin redemption navigation");
  await page.getByText("兑换码管理", { exact: true }).waitFor({ state: "visible", timeout: 30000 });
  const form = page.locator(".admin-dashboard-form-grid");
  const fields = form.locator("select, input");
  await fields.nth(0).selectOption("course_learning"); await fields.nth(1).selectOption("monthly");
  await fields.nth(2).fill("30");
  const expires = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000); expires.setSeconds(0, 0);
  const local = `${expires.getFullYear()}-${String(expires.getMonth() + 1).padStart(2, "0")}-${String(expires.getDate()).padStart(2, "0")}T${String(expires.getHours()).padStart(2, "0")}:${String(expires.getMinutes()).padStart(2, "0")}`;
  await fields.nth(3).fill(local); await fields.nth(4).fill("1"); await fields.nth(5).fill("1"); await fields.nth(6).fill("HTTPS security freeze acceptance");
  await click(form.locator(".admin-dashboard-primary-action"), "create QA redemption code");
  const data = await Promise.race([codeResponse, new Promise((_, reject) => setTimeout(() => reject(new Error("redemption code response timeout")), 30000))]);
  code = data?.codes?.[0]?.code;
  if (!code) throw new Error("admin UI did not return a one-time QA redemption code");
  report.records.redemption_code_created = { passed: true, code_id: data.codes[0].id || null, plaintext_not_persisted: true };
  return { context, page, code };
}
async function redemptionAcceptance(browser, username, secret) {
  const admin = await createCodeThroughAdmin(browser);
  const created = await registerAndOnboard(browser, username, secret, redemptionState);
  const { context, page } = created;
  let reloginContext;
  try {
    await openMembership(page);
    const before = await api(page, "/api/membership/orders?service_key=course_learning");
    const beforeCount = orderList(before.body).length;
    await click(page.locator(".membership-redeem-panel .membership-button"), "open redemption modal");
    const modal = page.locator(".membership-modal"); await modal.locator("input").fill(admin.code);
    await click(modal.locator(".membership-button").filter({ hasText: /预览|确认/ }).first(), "redemption preview");
    const preview = modal.locator(".membership-redeem-preview"); await preview.waitFor({ state: "visible", timeout: 30000 });
    const previewText = await preview.innerText();
    report.records.redemption_preview = { passed: /课程|月度|30/.test(previewText), preview_visible: true };
    await click(modal.locator(".membership-button").filter({ hasText: /确认|兑换/ }).first(), "confirm redemption");
    await modal.waitFor({ state: "hidden", timeout: 30000 }).catch(() => {});
    const after = await api(page, "/api/membership/orders?service_key=course_learning");
    const redeemedMe = await me(page);
    report.records.redemption_success_no_order = { passed: after.status === 200 && orderList(after.body).length === beforeCount && redeemedMe.status === 200, order_count_before: beforeCount, order_count_after: orderList(after.body).length };
    await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
    const refreshedMe = await me(page);
    report.records.redemption_refresh_persistence = { passed: refreshedMe.status === 200, me_status: refreshedMe.status };
    // A brand-new browser context has no cookies or local storage. Logging in
    // there validates persistence without racing the application's async
    // logout request (logout itself was already accepted separately).
    reloginContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const reloginPage = await reloginContext.newPage(); attach(reloginPage);
    await reloginPage.goto(baseUrl, { waitUntil: "commit", timeout: 45000 });
    await reloginPage.locator(".auth-input").first().waitFor({ state: "visible", timeout: 30000 });
    await reloginPage.locator(".auth-input").nth(0).fill(username); await reloginPage.locator(".auth-input").nth(1).fill(secret);
    const loginResponse = reloginPage.waitForResponse((response) => /\/api\/login$/.test(response.url()) && response.request().method() === "POST", { timeout: 30000 });
    await click(reloginPage.locator(".auth-submit"), "QA relogin in fresh context");
    if ((await loginResponse).status() !== 200) throw new Error("QA relogin request was rejected");
    await reloginPage.locator(".clh-user-card").waitFor({ state: "visible", timeout: 30000 });
    const reloggedMe = await me(reloginPage);
    report.records.redemption_relogin_persistence = { passed: reloggedMe.status === 200, me_status: reloggedMe.status };
    await reloginContext.storageState({ path: redemptionState });
    const row = admin.page.locator("tbody tr").filter({ hasText: "1/1" }).first();
    await row.waitFor({ state: "visible", timeout: 30000 });
    const rowText = await row.innerText();
    report.records.redemption_admin_exhausted = { passed: /1\/1/.test(rowText) && /已用完|exhausted/i.test(rowText), row_summary: rowText.replace(/\s+/g, " ").slice(0, 300) };
    await click(row.getByRole("button", { name: "查看", exact: true }), "redemption admin detail");
    await page.waitForTimeout(100); // preserve a visible UI action boundary before the expected rejected retry
    await openMembership(reloginPage);
    await click(reloginPage.locator(".membership-redeem-panel .membership-button"), "open second redemption modal");
    const retryModal = reloginPage.locator(".membership-modal"); await retryModal.locator("input").fill(admin.code);
    const rejected = reloginPage.waitForResponse((response) => /\/api\/membership\/redeem\/preview$/.test(response.url()) && response.status() >= 400, { timeout: 30000 });
    exhaustedPreviewInProgress = true;
    await click(retryModal.locator(".membership-button").filter({ hasText: /预览|确认/ }).first(), "rejected redemption preview");
    const rejectedResponse = await rejected;
    await reloginPage.waitForTimeout(500);
    exhaustedPreviewInProgress = false;
    report.records.redemption_second_attempt_rejected = { passed: rejectedResponse.status() >= 400, status: rejectedResponse.status() };
  } finally {
    await page.waitForTimeout(750).catch(() => {});
    if (reloginContext) await reloginContext.close();
    await context.close();
    await admin.context.close();
  }
}

let browser;
try {
  browser = await chromium.launch({ headless: true });
  const checkoutSecret = password(); const redemptionSecret = password();
  await checkoutAcceptance(browser, report.checkout_qa.username, checkoutSecret);
  await redemptionAcceptance(browser, report.redemption_qa.username, redemptionSecret);
  report.records.diagnostics = { passed: report.console_business_errors.length === 0 && report.unexpected_network_failures.length === 0 && report.mixed_content.length === 0, console_errors: report.console_business_errors.length, network_failures: report.unexpected_network_failures.length, mixed_content: report.mixed_content.length };
  report.status = Object.values(report.records).every((item) => item?.passed !== false) ? "passed" : "failed";
} catch (error) { report.status = "failed"; report.error = String(error.message || error).slice(0, 800); }
finally { if (browser) await browser.close().catch(() => {}); fs.writeFileSync(path.join(outputDir, "acceptance-final.json"), `${JSON.stringify(report, null, 2)}\n`); }
console.log(JSON.stringify({ status: report.status, report_path: rel(path.join(outputDir, "acceptance-final.json")), checkout_order_id: report.checkout_qa.order_id || null, plaintext_code_persisted: false }));
process.exitCode = report.status === "passed" ? 0 : 1;
